"""
Media handler and dispatcher for Video Conversion, Unzipping, and Zipper staging.
Routes incoming media based on the user's active mode.
"""

from __future__ import annotations

import uuid
import asyncio
import logging
from pathlib import Path
from hydrogram import Client, filters
from hydrogram.types import Message, InputMediaPhoto, InputMediaVideo

from bot.config import settings
from bot.database.users import is_whitelisted, get_user_mode
from bot.templates.cards import (
    access_denied_card,
    zipper_staging_card,
)
from bot.templates.buttons import zipper_actions_keyboard
from bot.utils.file_ops import (
    sanitize_filename,
    has_enough_free_space,
    get_task_dir,
    safe_remove_dir,
    format_bytes,
)
from bot.utils.progress import ProgressReporter
from bot.services.queue import queue_manager
from bot.services.converter import is_video_file, convert_to_mp4
from bot.services.unzipper import (
    is_archive_file,
    extract_archive_7z,
    get_and_validate_extracted_files,
    PasswordRequiredError,
)
from bot.services.zipper import add_file_to_staging

logger = logging.getLogger(__name__)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}

# In-memory dictionary for password-protected archives awaiting user reply
pending_password_archives: dict[int, dict] = {}


@Client.on_message((filters.video | filters.document | filters.photo | filters.audio) & filters.private)
async def handle_incoming_media(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    # Extract media metadata across videos, documents, photos, and audio
    media = message.video or message.document or message.photo or message.audio
    if not media:
        return

    if message.photo:
        file_name = f"photo_{message.id}.jpg"
        file_size = message.photo.file_size
        mime_type = "image/jpeg"
    elif message.audio:
        file_name = getattr(message.audio, "file_name", None) or f"audio_{message.id}.mp3"
        file_size = getattr(message.audio, "file_size", 0)
        mime_type = getattr(message.audio, "mime_type", "audio/mpeg")
    else:
        file_name = getattr(media, "file_name", None) or f"media_{message.id}"
        file_size = getattr(media, "file_size", 0)
        mime_type = getattr(media, "mime_type", "")

    file_name = sanitize_filename(file_name)

    mode = await get_user_mode(user_id)

    # ==========================================================================
    # 1. VIDEO CONVERTER MODE
    # ==========================================================================
    if mode == "convert":
        if not is_video_file(file_name, mime_type):
            await message.reply_text(
                "🎬 <b>Video Converter Active:</b>\n"
                "Please send a valid video file (e.g. MKV, AVI, WEBM, FLV, TS, MP4).\n"
                "<i>Switch modes with /mode if you intended to unzip or zip.</i>"
            )
            return

        # Check against Telegram 2 GB non-premium protocol limit
        if file_size > 2097152000:
            await message.reply_text(
                "⚠️ <b>File Exceeds Telegram Limit (2 GB):</b>\n"
                "Telegram does not allow bots to process files larger than 2 GB."
            )
            return

        # Process locally
        await process_video_locally(client, message, file_name, file_size)

    # ==========================================================================
    # 2. UNZIPPER MODE
    # ==========================================================================
    elif mode == "unzip":
        if not is_archive_file(file_name):
            await message.reply_text(
                "📦 <b>Unzipper Active:</b>\n"
                "Please send a valid archive file (.zip, .rar, .7z, .tar, .gz).\n"
                "<i>Switch modes with /mode if you intended to convert or zip.</i>"
            )
            return

        if file_size > 2097152000:
            await message.reply_text(
                "⚠️ <b>Archive Exceeds Telegram Limit (2 GB):</b>\n"
                "Telegram does not allow bots to process files larger than 2 GB."
            )
            return

        await process_unzip_locally(client, message, file_name, file_size)

    # ==========================================================================
    # 3. ZIPPER MODE (Multi-file collector)
    # ==========================================================================
    elif mode == "zip":
        task_id = str(uuid.uuid4())[:8]
        task_dir = get_task_dir(user_id, task_id)
        status_msg = await message.reply_text("📥 <i>Downloading file to zip staging...</i>")

        reporter = ProgressReporter(
            status_message=status_msg,
            task_name=file_name,
            task_id=task_id,
            phase="Downloading",
            total_bytes=file_size,
        )
        await queue_manager.register_task(task_id, user_id, reporter)

        try:
            download_dest = task_dir / file_name
            downloaded_res = await client.download_media(
                message=message,
                file_name=str(download_dest.resolve()),
                progress=reporter.pyrogram_callback,
            )

            actual_file = Path(downloaded_res) if downloaded_res else download_dest
            if not actual_file.exists():
                raise FileNotFoundError(f"Failed to save staged file: {download_dest}")

            count, total_staged, latest = await add_file_to_staging(
                user_id=user_id,
                source_file=actual_file,
                original_filename=file_name,
            )

            await status_msg.edit_text(
                text=zipper_staging_card(count, total_staged, latest),
                reply_markup=zipper_actions_keyboard(),
            )
        except Exception as e:
            logger.error("Failed to stage file for zipper: %s", e)
            await status_msg.edit_text(f"⚠️ <b>Failed to stage file:</b> <code>{e}</code>")
        finally:
            await queue_manager.unregister_task(task_id)
            safe_remove_dir(task_dir)


@Client.on_message(filters.text & filters.private & filters.reply)
async def handle_archive_password_reply(client: Client, message: Message):
    """Handles password submission for encrypted archives awaiting extraction."""
    user_id = message.from_user.id
    if user_id not in pending_password_archives:
        return

    ctx = pending_password_archives[user_id]
    if message.reply_to_message.id != ctx["status_msg"].id:
        return

    password = message.text.strip()
    if password.lower() == "/cancel":
        del pending_password_archives[user_id]
        safe_remove_dir(ctx["task_dir"])
        await queue_manager.unregister_task(ctx["task_id"])
        await ctx["status_msg"].edit_text("❌ <b>Archive extraction aborted.</b>")
        return

    status_msg = ctx["status_msg"]
    task_id = ctx["task_id"]
    task_dir = ctx["task_dir"]
    arch_file = ctx["arch_file"]
    file_name = ctx["file_name"]

    await status_msg.edit_text("🔓 <i>Password received. Verifying and extracting...</i>")

    reporter = ctx["reporter"]
    extract_dest = task_dir / "extracted"

    try:
        success = await extract_archive_7z(
            archive_path=arch_file,
            dest_dir=extract_dest,
            task_id=task_id,
            reporter=reporter,
            password=password,
        )

        if not success:
            await status_msg.edit_text("⚠️ <b>Extraction failed with provided password.</b>")
            del pending_password_archives[user_id]
            safe_remove_dir(task_dir)
            await queue_manager.unregister_task(task_id)
            return

        # Extraction succeeded with password! Proceed to deliver files
        del pending_password_archives[user_id]
        await deliver_extracted_contents(client, message, extract_dest, status_msg, reporter)

    except PasswordRequiredError:
        await status_msg.edit_text(
            "❌ <b>Incorrect password!</b>\n\n"
            f"<code>{file_name}</code> could not be unlocked.\n\n"
            "👉 <b>Reply again to this message with the correct password</b>, or send /cancel to abort."
        )
    except Exception as e:
        logger.error("Error during password extraction: %s", e)
        await status_msg.edit_text(f"⚠️ <b>Extraction error:</b> <code>{e}</code>")
        del pending_password_archives[user_id]
        safe_remove_dir(task_dir)
        await queue_manager.unregister_task(task_id)


async def deliver_extracted_contents(
    client: Client,
    message: Message,
    extract_dest: Path,
    status_msg: Message,
    reporter: ProgressReporter,
):
    """
    Delivers extracted files:
    - Photos (JPG/PNG/WEBP) & Videos (MP4) in native Telegram Albums (up to 10 per album).
    - Documents (PDF, ZIP, APK, TXT, etc.) as clean individual files.
    """
    valid_files, oversized = get_and_validate_extracted_files(extract_dest)
    if not valid_files and not oversized:
        await status_msg.edit_text("⚠️ <b>Archive was empty or contained no valid files.</b>")
        return

    # Inform user if files were skipped due to 2 GB limit
    if oversized:
        oversized_lines = [f"• <code>{f}</code> ({format_bytes(s)})" for f, s in oversized]
        await client.send_message(
            chat_id=message.chat.id,
            text=(
                "⚠️ <b>The following extracted files exceed the Telegram 2 GB limit and were skipped:</b>\n"
                + "\n".join(oversized_lines)
            ),
        )

    # Separate media files (for albums) and document files
    media_files = [f for f in valid_files if f.suffix.lower() in (PHOTO_EXTENSIONS | VIDEO_EXTENSIONS)]
    doc_files = [f for f in valid_files if f.suffix.lower() not in (PHOTO_EXTENSIONS | VIDEO_EXTENSIONS)]

    # 1. Deliver visual media in standard Telegram albums (up to 10 per album)
    album_chunks = [media_files[i:i + 10] for i in range(0, len(media_files), 10)]
    total_albums = len(album_chunks)

    for idx, chunk in enumerate(album_chunks, 1):
        if reporter.is_cancelled:
            break

        reporter.set_phase(f"Uploading Album ({idx}/{total_albums})")

        if len(chunk) == 1:
            item = chunk[0]
            if item.suffix.lower() in PHOTO_EXTENSIONS:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=str(item.resolve()),
                    caption=f"🖼️ <code>{item.name}</code>",
                )
            else:
                await client.send_video(
                    chat_id=message.chat.id,
                    video=str(item.resolve()),
                    caption=f"🎬 <code>{item.name}</code>",
                )
        else:
            media_group = []
            for item in chunk:
                if item.suffix.lower() in PHOTO_EXTENSIONS:
                    media_group.append(InputMediaPhoto(media=str(item.resolve()), caption=f"<code>{item.name}</code>"))
                else:
                    media_group.append(InputMediaVideo(media=str(item.resolve()), caption=f"<code>{item.name}</code>"))

            await client.send_media_group(chat_id=message.chat.id, media=media_group)

        await asyncio.sleep(1.5)  # FloodWait throttle between albums

    # 2. Deliver non-media document files
    total_docs = len(doc_files)
    for idx, item in enumerate(doc_files, 1):
        if reporter.is_cancelled:
            break

        reporter.set_phase(f"Uploading File ({idx}/{total_docs})", total_bytes=item.stat().st_size)
        await client.send_document(
            chat_id=message.chat.id,
            document=str(item.resolve()),
            caption=f"📄 <code>{item.name}</code>",
            progress=reporter.pyrogram_callback,
        )
        await asyncio.sleep(1.2)  # Delay between document uploads

    if not reporter.is_cancelled:
        summary_text = f"✅ <b>Extraction complete!</b>\n"
        if media_files:
            summary_text += f"• Delivered <b>{len(media_files)}</b> photos/videos in <b>{total_albums}</b> albums.\n"
        if doc_files:
            summary_text += f"• Delivered <b>{len(doc_files)}</b> documents.\n"
        await status_msg.edit_text(summary_text)


async def process_video_locally(client: Client, message: Message, file_name: str, file_size: int):
    """Local video download, FFmpeg transcode, and upload workflow."""
    user_id = message.from_user.id
    task_id = str(uuid.uuid4())[:8]
    task_dir = get_task_dir(user_id, task_id)

    if not has_enough_free_space(file_size * 2):
        await message.reply_text("⚠️ <b>Insufficient disk space on host node to process this video.</b>")
        return

    status_msg = await message.reply_text("📥 <i>Connecting and preparing download...</i>")
    reporter = ProgressReporter(
        status_message=status_msg,
        task_name=file_name,
        task_id=task_id,
        phase="Downloading",
        total_bytes=file_size,
    )
    await queue_manager.register_task(task_id, user_id, reporter)

    try:
        async with queue_manager.acquire_slot():
            # Download
            in_file = task_dir / file_name
            await client.download_media(
                message=message,
                file_name=str(in_file.resolve()),
                progress=reporter.pyrogram_callback,
            )

            if reporter.is_cancelled:
                return

            # Convert to MP4
            stem = in_file.stem
            out_file = task_dir / f"{stem}_converted.mp4"
            success, metadata, thumb_path = await convert_to_mp4(
                input_file=in_file,
                output_file=out_file,
                task_id=task_id,
                reporter=reporter,
            )

            if not success or not out_file.exists():
                if not reporter.is_cancelled:
                    await status_msg.edit_text("⚠️ <b>Video conversion failed. Check format or codec compatibility.</b>")
                return

            # Upload converted video
            reporter.set_phase("Uploading", total_bytes=out_file.stat().st_size)
            await client.send_video(
                chat_id=message.chat.id,
                video=str(out_file.resolve()),
                caption=f"🎬 <b>Converted to MP4:</b> <code>{out_file.name}</code>",
                duration=metadata.get("duration", 0),
                width=metadata.get("width", 1280),
                height=metadata.get("height", 720),
                thumb=str(thumb_path.resolve()) if thumb_path else None,
                supports_streaming=True,
                progress=reporter.pyrogram_callback,
            )

            await status_msg.delete()

    except Exception as e:
        logger.error("Error processing video locally: %s", e)
        if not reporter.is_cancelled:
            await status_msg.edit_text(f"⚠️ <b>Processing error:</b> <code>{e}</code>")
    finally:
        await queue_manager.unregister_task(task_id)
        safe_remove_dir(task_dir)


async def process_unzip_locally(client: Client, message: Message, file_name: str, file_size: int):
    """Local archive download, extraction, and media album / document upload workflow."""
    user_id = message.from_user.id
    task_id = str(uuid.uuid4())[:8]
    task_dir = get_task_dir(user_id, task_id)

    if not has_enough_free_space(file_size * 2):
        await message.reply_text("⚠️ <b>Insufficient disk space on host node to extract this archive.</b>")
        return

    status_msg = await message.reply_text("📥 <i>Preparing archive download...</i>")
    reporter = ProgressReporter(
        status_message=status_msg,
        task_name=file_name,
        task_id=task_id,
        phase="Downloading",
        total_bytes=file_size,
    )
    await queue_manager.register_task(task_id, user_id, reporter)

    try:
        async with queue_manager.acquire_slot():
            arch_file = task_dir / file_name
            await client.download_media(
                message=message,
                file_name=str(arch_file.resolve()),
                progress=reporter.pyrogram_callback,
            )

            if reporter.is_cancelled:
                return

            extract_dest = task_dir / "extracted"

            try:
                success = await extract_archive_7z(
                    archive_path=arch_file,
                    dest_dir=extract_dest,
                    task_id=task_id,
                    reporter=reporter,
                )
            except PasswordRequiredError:
                # Prompt user for password and keep context
                pending_password_archives[user_id] = {
                    "task_id": task_id,
                    "task_dir": task_dir,
                    "arch_file": arch_file,
                    "file_name": file_name,
                    "file_size": file_size,
                    "status_msg": status_msg,
                    "reporter": reporter,
                }
                await status_msg.edit_text(
                    "🔐 <b>Password-Protected Archive Detected!</b>\n\n"
                    f"<code>{file_name}</code> is protected with a password.\n\n"
                    "👉 <b>Reply directly to this message with the password</b> to extract your files.\n"
                    "<i>(Send /cancel to discard this archive)</i>"
                )
                return

            if not success:
                if not reporter.is_cancelled:
                    await status_msg.edit_text("⚠️ <b>Extraction failed or archive format unsupported.</b>")
                return

            # Deliver files in standard albums and documents
            await deliver_extracted_contents(client, message, extract_dest, status_msg, reporter)

    except Exception as e:
        logger.error("Error processing archive locally: %s", e)
        if not reporter.is_cancelled:
            await status_msg.edit_text(f"⚠️ <b>Extraction error:</b> <code>{e}</code>")
    finally:
        # If awaiting password, do not purge task_dir yet
        if user_id not in pending_password_archives:
            await queue_manager.unregister_task(task_id)
            safe_remove_dir(task_dir)
