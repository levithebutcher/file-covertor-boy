"""
Hydrogram Telegram MTProto client initialization with lazy loading.
Prevents RuntimeError: There is no current event loop in thread 'MainThread' on Python 3.11+.
"""

import logging
from pathlib import Path
from hydrogram import Client
from bot.config import settings

logger = logging.getLogger(__name__)

# Ensure sessions directory exists
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class LazyClientProxy:
    """
    Lazy proxy for Hydrogram Client.
    Delays instantiation until an asyncio event loop is actively running.
    """
    def __init__(self):
        self._client: Client | None = None

    def get_instance(self) -> Client:
        if self._client is None:
            self._client = Client(
                name=str((SESSIONS_DIR / "nexus_bot").resolve()),
                api_id=settings.api_id,
                api_hash=settings.api_hash,
                bot_token=settings.bot_token,
                plugins=dict(root="bot/handlers"),
                workers=min(4, max(2, settings.max_concurrent_jobs * 2)),
                sleep_threshold=30,
            )
        return self._client

    def __getattr__(self, name):
        return getattr(self.get_instance(), name)


bot_client = LazyClientProxy()
