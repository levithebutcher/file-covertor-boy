"""
General callback query handlers for cancellation, dialogs, and zipper actions.
"""

from __future__ import annotations

import uuid
import logging
from pathlib import Path
from hydrogram import Client, filters
from hydrogram.types import CallbackQuery, Message
from bot.services.queue import queue_manager
from bot.services.zipper import clear_staging, create_zip_package, get_staging_stats
from bot.utils.progress import ProgressReporter
from bot.utils.file_ops import get_task_dir, safe_remove_dir

logger = logging.getLogger(__name__)


@Client.on_callback_query(filters.regex(r"^cancel_task:(.+)$"))
async def handle_cancel_task(client: Client, callback: CallbackQuery):
    task_id = callback.matches[0].group(1)
    success = await queue_manager.cancel_task(task_id)
    if success:
        await callback.answer("Task cancelled.", show_alert=False)
        try:
            await callback.message.edit_text("❌ <b>Task Cancelled.</b> Temporary files deleted.")
        except Exception:
            pass
    else:
        await callback.answer("Task already finished or not found.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^mode_info$"))
async def handle_mode_info(client: Client, callback: CallbackQuery):
    info_text = (
        "🤖 BOT MODES:\n\n"
        "1. 🎬 VIDEO CONVERTER:\n"
        "Converts MKV, AVI, WEBM, FLV, TS, etc. to streaming MP4 with live progress.\n\n"
        "2. 📦 UNZIPPER:\n"
        "Extracts .zip, .rar, .7z, .tar, .gz archives and sends files back sequentially.\n\n"
        "3. 🗜️ ZIPPER:\n"
        "Send multiple files, then tap 'Create .ZIP Now' to bundle and upload."
    )
    await callback.answer(info_text, show_alert=True)


@Client.on_callback_query(filters.regex(r"^close_menu$"))
async def handle_close_menu(client: Client, callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^zip_clear$"))
async def handle_zip_clear(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    clear_staging(user_id)
    await callback.answer("Staged files cleared.", show_alert=False)
    await callback.message.edit_text("🗑️ <b>Zip batch staging cleared.</b>")


async def run_zip_package_and_upload(client: Client, chat_id: int, user_id: int, status_msg: Message):
    """Core executor to compress staged files into a zip package and upload to Telegram."""
    count, total_size, _ = get_staging_stats(user_id)
    if count == 0:
        await status_msg.edit_text("⚠️ <b>No files in staging!</b>\nSend files or photos first while in Zipper mode (/zip).")
        return

    task_id = str(uuid.uuid4())[:8]
    await status_msg.edit_text("🗜️ <b>Compressing staged files...</b>")

    reporter = ProgressReporter(
        status_message=status_msg,
        task_name="Creating Archive.zip",
        task_id=task_id,
        phase="Zipping",
        total_bytes=total_size,
    )
    await queue_manager.register_task(task_id, user_id, reporter)

    task_dir = get_task_dir(user_id, task_id)
    try:
        async with queue_manager.acquire_slot():
            archives = await create_zip_package(user_id, task_id, task_dir, reporter)

            if not archives:
                if reporter.is_cancelled:
                    await status_msg.edit_text("❌ <b>Zipping cancelled.</b>")
                else:
                    await status_msg.edit_text("⚠️ <b>Failed to create zip archive.</b>")
                return

            # Upload archives
            for idx, arch in enumerate(archives, 1):
                part_label = f" (Part {idx}/{len(archives)})" if len(archives) > 1 else ""
                reporter.set_phase(f"Uploading{part_label}", total_bytes=arch.stat().st_size)

                await client.send_document(
                    chat_id=chat_id,
                    document=str(arch.resolve()),
                    caption=f"🗜️ <b>Archive Ready:</b> <code>{arch.name}</code>{part_label}",
                    progress=reporter.pyrogram_callback,
                )

            # Clear staging upon success
            clear_staging(user_id)
            await status_msg.edit_text(f"✅ <b>Successfully packaged and sent {count} files!</b>")

    except Exception as e:
        logger.error("Error creating zip batch: %s", e)
        await status_msg.edit_text(f"⚠️ <b>Error during zipping:</b> <code>{e}</code>")
    finally:
        await queue_manager.unregister_task(task_id)
        safe_remove_dir(task_dir)


@Client.on_callback_query(filters.regex(r"^zip_finish$"))
async def handle_zip_finish(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    count, _, _ = get_staging_stats(user_id)
    if count == 0:
        await callback.answer("No files in staging! Send files first.", show_alert=True)
        return

    await callback.answer("Building archive...", show_alert=False)
    await run_zip_package_and_upload(client, callback.message.chat.id, user_id, callback.message)


@Client.on_message(filters.command(["finish", "done", "makezip", "createzip"]) & filters.private)
async def handle_cmd_finish_zip(client: Client, message: Message):
    """Slash command shortcut to trigger zip bundling without button."""
    user_id = message.from_user.id
    count, _, _ = get_staging_stats(user_id)
    if count == 0:
        await message.reply_text("⚠️ <b>No files in staging!</b>\nSend some files or photos first in Zipper mode (/zip).")
        return

    status_msg = await message.reply_text("🗜️ <i>Starting zip archive creation...</i>")
    await run_zip_package_and_upload(client, message.chat.id, user_id, status_msg)


@Client.on_message(filters.command(["clear", "clearzip"]) & filters.private)
async def handle_cmd_clear_zip(client: Client, message: Message):
    """Slash command to clear staged zip files."""
    user_id = message.from_user.id
    clear_staging(user_id)
    await message.reply_text("🗑️ <b>Zip batch staging cleared.</b>")
