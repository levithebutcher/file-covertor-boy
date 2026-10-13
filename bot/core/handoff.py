"""
Distributed host handoff coordinator for Render Free and Google Colab.
Prevents dual-polling Telegram session conflicts via MongoDB master lock.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bot.config import settings
from bot.core.client import bot_client
from bot.database.jobs import (
    acquire_host_lock,
    heartbeat_host_lock,
    release_host_lock,
    get_lock_state,
    get_pending_jobs,
    update_job_status,
)
from bot.utils.file_ops import get_task_dir, safe_remove_dir
from bot.utils.progress import ProgressReporter
from bot.services.converter import convert_to_mp4
from bot.services.unzipper import extract_archive_7z, get_and_validate_extracted_files

logger = logging.getLogger(__name__)


class RenderHandoffWatcher:
    """
    Runs on Render Free.
    Monitors MongoDB master lock. If Colab claims the lock, pauses Render's
    Telegram client to avoid session conflict. Resumes automatically when Colab stops.
    """
    def __init__(self):
        self.is_running = False
        self.is_client_paused = False

    async def start(self):
        self.is_running = True
        logger.info("Starting Render Handoff Watcher loop...")
        while self.is_running:
            try:
                lock = await get_lock_state()
                active_host = lock.get("active_host", "render")
                last_hb = lock.get("heartbeat", datetime.now(timezone.utc))

                # Ensure datetime is timezone-aware
                if last_hb.tzinfo is None:
                    last_hb = last_hb.replace(tzinfo=timezone.utc)

                now = datetime.now(timezone.utc)
                seconds_since_hb = (now - last_hb).total_seconds()

                if active_host == "colab" and seconds_since_hb <= 45:
                    # Colab is actively processing
                    if not self.is_client_paused:
                        logger.warning("Colab worker active! Pausing Render Telegram client...")
                        try:
                            if bot_client.is_connected:
                                await bot_client.stop()
                        except Exception as e:
                            logger.error("Error pausing Telegram client on Render: %s", e)
                        self.is_client_paused = True
                else:
                    # Render should be active
                    if self.is_client_paused or active_host != "render":
                        logger.info("Colab worker idle or released. Resuming Render Telegram client...")
                        await acquire_host_lock("render")
                        try:
                            if not bot_client.is_connected:
                                await bot_client.start()
                        except Exception as e:
                            logger.error("Error resuming Telegram client on Render: %s", e)
                        self.is_client_paused = False

                    # Send Render heartbeat
                    await heartbeat_host_lock("render")

            except Exception as e:
                logger.error("Error in Render watcher loop: %s", e)

            await asyncio.sleep(10)

    def stop(self):
        self.is_running = False


class ColabWorkerEngine:
    """
    Runs on Google Colab.
    Acquires master lock, pauses Render, processes pending large-file jobs,
    and returns lock to Render when finished.
    """
    def __init__(self):
        self.is_running = False

    async def run(self):
        logger.info("Google Colab worker initializing...")
        # Step 1: Claim master lock
        acquired = await acquire_host_lock("colab")
        if not acquired:
            logger.warning("Could not acquire master lock immediately. Retrying...")
            await asyncio.sleep(5)
            await acquire_host_lock("colab")

        logger.info("Master lock claimed by Colab. Render client will pause.")
        await asyncio.sleep(12)  # Give Render watcher a moment to pause

        # Step 2: Start Telegram client
        if not bot_client.is_connected:
            await bot_client.start()

        self.is_running = True
        logger.info("Colab Telegram client connected. Checking for pending overflow jobs...")

        # Heartbeat background task
        hb_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while self.is_running:
                pending_jobs = await get_pending_jobs()
                if not pending_jobs:
                    logger.info("No pending jobs remaining for Colab. Sleeping...")
                    await asyncio.sleep(10)
                    continue

                for job in pending_jobs:
                    await self._process_job(job)

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Colab worker received stop signal.")
        finally:
            self.is_running = False
            hb_task.cancel()
            logger.info("Releasing master lock back to Render...")
            await release_host_lock("colab")
            if bot_client.is_connected:
                await bot_client.stop()
            logger.info("Colab worker finished. Render will resume automatically.")

    async def _heartbeat_loop(self):
        while self.is_running:
            await heartbeat_host_lock("colab")
            await asyncio.sleep(10)

    async def _process_job(self, job: dict):
        job_id = job["job_id"]
        chat_id = job["chat_id"]
        message_id = job["message_id"]
        file_name = job["file_name"]
        file_size = job["file_size"]
        mode = job["mode"]

        logger.info("Colab processing job %s (%s, %d bytes)", job_id, file_name, file_size)
        await update_job_status(job_id, "processing")

        try:
            status_msg = await bot_client.send_message(
                chat_id=chat_id,
                text=f"🚀 <b>Colab Worker Connected!</b>\nProcessing queued large file: <code>{file_name}</code>",
            )
            src_msg = await bot_client.get_messages(chat_id=chat_id, message_ids=message_id)

            task_dir = get_task_dir(chat_id, job_id)
            reporter = ProgressReporter(
                status_message=status_msg,
                task_name=file_name,
                task_id=job_id,
                phase="Downloading",
                total_bytes=file_size,
            )

            # Download
            in_file = task_dir / file_name
            await bot_client.download_media(
                message=src_msg,
                file_name=str(in_file.resolve()),
                progress=reporter.pyrogram_callback,
            )

            if mode == "convert":
                out_file = task_dir / f"{in_file.stem}_converted.mp4"
                success, metadata, thumb_path = await convert_to_mp4(
                    input_file=in_file,
                    output_file=out_file,
                    task_id=job_id,
                    reporter=reporter,
                )
                if success and out_file.exists():
                    reporter.set_phase("Uploading", total_bytes=out_file.stat().st_size)
                    await bot_client.send_video(
                        chat_id=chat_id,
                        video=str(out_file.resolve()),
                        caption=f"🎬 <b>Converted on Colab:</b> <code>{out_file.name}</code>",
                        duration=metadata.get("duration", 0),
                        width=metadata.get("width", 1280),
                        height=metadata.get("height", 720),
                        thumb=str(thumb_path.resolve()) if thumb_path else None,
                        supports_streaming=True,
                        progress=reporter.pyrogram_callback,
                    )
                    await update_job_status(job_id, "completed")
                    await status_msg.delete()
                else:
                    await status_msg.edit_text("⚠️ <b>Conversion failed on Colab.</b>")
                    await update_job_status(job_id, "failed", error="Conversion failed")

            elif mode == "unzip":
                extract_dest = task_dir / "extracted"
                success = await extract_archive_7z(
                    archive_path=in_file,
                    dest_dir=extract_dest,
                    task_id=job_id,
                    reporter=reporter,
                )
                if success:
                    valid_files, oversized = get_and_validate_extracted_files(extract_dest)
                    for item in valid_files:
                        reporter.set_phase(f"Uploading: {item.name}", total_bytes=item.stat().st_size)
                        await bot_client.send_document(
                            chat_id=chat_id,
                            document=str(item.resolve()),
                            caption=f"📄 <code>{item.name}</code>",
                            progress=reporter.pyrogram_callback,
                        )
                        await asyncio.sleep(1.2)
                    await update_job_status(job_id, "completed")
                    await status_msg.edit_text(f"✅ <b>Colab extraction complete! Sent {len(valid_files)} files.</b>")
                else:
                    await status_msg.edit_text("⚠️ <b>Extraction failed on Colab.</b>")
                    await update_job_status(job_id, "failed", error="Extraction failed")

            safe_remove_dir(task_dir)

        except Exception as e:
            logger.error("Error processing job %s on Colab: %s", job_id, e)
            await update_job_status(job_id, "failed", error=str(e))
