"""
Asynchronous queue, concurrency control, and cancellation registry.
Limits concurrent tasks on Render Free to protect 512 MB memory limit.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from bot.config import settings

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, max_concurrent: int = 1):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire_slot(self):
        """Acquire a concurrency slot before beginning heavy conversion/archiving."""
        await self.semaphore.acquire()
        try:
            yield
        finally:
            self.semaphore.release()

    async def register_task(
        self,
        task_id: str,
        user_id: int,
        reporter: Any,
        process: Optional[asyncio.subprocess.Process] = None,
        asyncio_task: Optional[asyncio.Task] = None,
    ):
        """Register a running task for live cancellation."""
        async with self._lock:
            self.active_tasks[task_id] = {
                "user_id": user_id,
                "reporter": reporter,
                "process": process,
                "task": asyncio_task,
            }
            logger.info("Task %s registered for user %d (Active total: %d)", task_id, user_id, len(self.active_tasks))

    async def set_process(self, task_id: str, process: asyncio.subprocess.Process):
        """Attach a newly spawned subprocess to the registered task."""
        async with self._lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["process"] = process

    async def unregister_task(self, task_id: str):
        """Unregister completed or aborted task."""
        async with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
                logger.info("Task %s unregistered (Active total: %d)", task_id, len(self.active_tasks))

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task immediately and terminate its child process."""
        async with self._lock:
            if task_id not in self.active_tasks:
                return False

            task_info = self.active_tasks[task_id]
            logger.info("Aborting task %s on user cancellation request", task_id)

            # Mark reporter as cancelled
            if task_info.get("reporter"):
                task_info["reporter"].cancel()

            # Terminate running subprocess (ffmpeg / 7z)
            proc = task_info.get("process")
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    logger.info("Sent SIGTERM to process of task %s", task_id)
                except Exception as e:
                    logger.warning("Error terminating process: %s", e)

            # Cancel asyncio task if attached
            atask = task_info.get("task")
            if atask and not atask.done():
                atask.cancel()

            return True


# Global queue manager instance
queue_manager = QueueManager(max_concurrent=settings.max_concurrent_jobs)
