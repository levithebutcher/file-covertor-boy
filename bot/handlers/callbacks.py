"""
General callback query handlers for cancellation, dialogs, and zipper actions.
"""

import uuid
import logging
from pathlib import Path
from hydrogram import Client, filters
from hydrogram.types import CallbackQuery
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
        "✨ NEXUS MEDIA SUITE MODES:\n\n"
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


@Client.on_callback_query(filters.regex(r"^zip_finish$"))
async def handle_zip_finish(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    count, total_size, _ = get_staging_stats(user_id)
    if count == 0:
        await callback.answer("No files in staging! Send files first.", show_alert=True)
        return

    await callback.answer("Building archive...", show_alert=False)
    task_id = str(uuid.uuid4())[:8]
    status_msg = await callback.message.edit_text("🗜️ <b>Compressing staged files...</b>")

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
                    chat_id=callback.message.chat.id,
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
