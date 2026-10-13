"""
Media handler and dispatcher for Video Conversion, Unzipping, and Zipper staging.
Routes incoming media based on the user's active mode and enforces threshold handoff.
"""

import uuid
import asyncio
import logging
from pathlib import Path
from hydrogram import Client, filters
from hydrogram.types import Message

from bot.config import settings
from bot.database.users import is_whitelisted, get_user_mode
from bot.database.jobs import create_pending_job
from bot.templates.cards import (
    access_denied_card,
    large_file_card,
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
from bot.services.unzipper import is_archive_file, extract_archive_7z, get_and_validate_extracted_files
from bot.services.zipper import add_file_to_staging

logger = logging.getLogger(__name__)


@Client.on_message((filters.video | filters.document) & filters.private)
async def handle_incoming_media(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    # Extract media metadata
    media = message.video or message.document
    if not media:
        return

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

        # Check file size against Render memory/disk threshold
        if file_size > settings.big_file_threshold_bytes:
            job_id = await create_pending_job(
                chat_id=message.chat.id,
                message_id=message.id,
                file_id=media.file_id,
                file_name=file_name,
                file_size=file_size,
                mode="convert",
            )
            logger.info("Queued large video job %s (%d bytes) for Colab handoff", job_id, file_size)
            await message.reply_text(
                large_file_card(file_name, file_size, settings.big_file_threshold_mb)
            )
            return

        # Process locally on Render
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

        if file_size > settings.big_file_threshold_bytes:
            job_id = await create_pending_job(
                chat_id=message.chat.id,
                message_id=message.id,
                file_id=media.file_id,
                file_name=file_name,
                file_size=file_size,
                mode="unzip",
            )
            logger.info("Queued large archive job %s (%d bytes) for Colab handoff", job_id, file_size)
            await message.reply_text(
                large_file_card(file_name, file_size, settings.big_file_threshold_mb)
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
            await client.download_media(
                message=message,
                file_name=str(download_dest.resolve()),
                progress=reporter.pyrogram_callback,
            )

            count, total_staged, latest = await add_file_to_staging(
                user_id=user_id,
                source_file=download_dest,
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
    """Local archive download, 7z extraction, and multi-file upload workflow."""
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
            success = await extract_archive_7z(
                archive_path=arch_file,
                dest_dir=extract_dest,
                task_id=task_id,
                reporter=reporter,
            )

            if not success:
                if not reporter.is_cancelled:
                    await status_msg.edit_text("⚠️ <b>Extraction failed or archive format unsupported.</b>")
                return

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
                    )
                )

            # Upload valid files sequentially
            total_items = len(valid_files)
            for idx, item in enumerate(valid_files, 1):
                if reporter.is_cancelled:
                    break

                reporter.set_phase(f"Uploading ({idx}/{total_items})", total_bytes=item.stat().st_size)
                await client.send_document(
                    chat_id=message.chat.id,
                    document=str(item.resolve()),
                    caption=f"📄 <code>{item.name}</code>",
                    progress=reporter.pyrogram_callback,
                )
                await asyncio.sleep(1.2)  # Delay between uploads to prevent Telegram flood penalties

            if not reporter.is_cancelled:
                await status_msg.edit_text(f"✅ <b>Extraction complete! Sent {total_items} files.</b>")

    except Exception as e:
        logger.error("Error processing archive locally: %s", e)
        if not reporter.is_cancelled:
            await status_msg.edit_text(f"⚠️ <b>Extraction error:</b> <code>{e}</code>")
    finally:
        await queue_manager.unregister_task(task_id)
        safe_remove_dir(task_dir)
