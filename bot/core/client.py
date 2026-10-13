"""
Hydrogram Telegram MTProto client initialization.
"""

import logging
from pathlib import Path
from hydrogram import Client
from bot.config import settings

logger = logging.getLogger(__name__)

# Ensure sessions directory exists
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

bot_client = Client(
    name=str((SESSIONS_DIR / "nexus_bot").resolve()),
    api_id=settings.api_id,
    api_hash=settings.api_hash,
    bot_token=settings.bot_token,
    plugins=dict(root="bot/handlers"),
    workers=min(4, max(2, settings.max_concurrent_jobs * 2)),
    sleep_threshold=30,
)
