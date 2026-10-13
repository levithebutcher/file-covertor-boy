"""
Live throttled progress reporter for Telegram messages with FloodWait handling and cancellation.
"""

import time
import asyncio
import logging
from typing import Optional
from hydrogram.types import Message
from hydrogram.errors import FloodWait, MessageNotModified
from bot.templates.cards import progress_card
from bot.templates.buttons import progress_cancel_keyboard

logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 4.5  # Seconds between Telegram message updates to prevent rate limits


class ProgressReporter:
    def __init__(
        self,
        status_message: Message,
        task_name: str,
        task_id: str,
        phase: str = "Processing",
        total_bytes: int = 0,
    ):
        self.status_message = status_message
        self.task_name = task_name
        self.task_id = task_id
        self.phase = phase
        self.total_bytes = total_bytes
        self.start_time = time.time()
        self.last_update_time = 0.0
        self.is_cancelled = False
        self._lock = asyncio.Lock()

    def set_phase(self, phase: str, total_bytes: Optional[int] = None):
        """Transition to a new phase (e.g. Downloading -> Converting -> Uploading)."""
        self.phase = phase
        if total_bytes is not None and total_bytes > 0:
            self.total_bytes = total_bytes
        self.start_time = time.time()
        self.last_update_time = 0.0

    def cancel(self):
        """Mark task as cancelled."""
        self.is_cancelled = True

    async def update(self, current_bytes: int, total_bytes: Optional[int] = None, force: bool = False):
        """Update progress with rate-limiting."""
        if self.is_cancelled:
            return

        if total_bytes and total_bytes > 0:
            self.total_bytes = total_bytes

        now = time.time()
        elapsed = now - self.start_time

        # Update only if interval has passed or forced
        if not force and (now - self.last_update_time < UPDATE_INTERVAL):
            return

        async with self._lock:
            # Re-check under lock
            if not force and (now - self.last_update_time < UPDATE_INTERVAL):
                return
            self.last_update_time = now

            # Calculate metrics
            speed = current_bytes / elapsed if elapsed > 0 else 0.0
            percentage = (current_bytes / self.total_bytes * 100.0) if self.total_bytes > 0 else 0.0
            eta = ((self.total_bytes - current_bytes) / speed) if (speed > 0 and self.total_bytes > 0) else 0.0

            text = progress_card(
                task_name=self.task_name,
                phase=self.phase,
                current_bytes=current_bytes,
                total_bytes=self.total_bytes,
                speed_bytes_sec=speed,
                eta_seconds=eta,
                percentage=percentage,
            )

            try:
                await self.status_message.edit_text(
                    text=text,
                    reply_markup=progress_cancel_keyboard(self.task_id),
                )
            except FloodWait as e:
                logger.warning("FloodWait of %d seconds encountered during progress update", e.value)
                await asyncio.sleep(e.value)
            except MessageNotModified:
                pass
            except Exception as e:
                logger.debug("Minor exception while editing progress message: %s", e)

    async def pyrogram_callback(self, current: int, total: int):
        """Adapter callback compatible with Hydrogram download/upload progress hooks."""
        if self.is_cancelled:
            raise asyncio.CancelledError("Task was cancelled by user.")
        await self.update(current_bytes=current, total_bytes=total)
