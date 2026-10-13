"""
MongoDB connection and client lifecycle manager using Motor.
Provides fallback in-memory store if MONGO_URI is not configured.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bot.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.is_connected: bool = False

        # In-memory fallbacks when running without external MongoDB Atlas
        self._mem_users: dict[int, dict] = {}
        self._mem_jobs: dict[str, dict] = {}
        self._mem_lock: dict[str, any] = {
            "active_host": "render",
            "heartbeat": datetime.now(timezone.utc),
            "colab_waiting": False,
        }

    async def connect(self) -> bool:
        """Establish connection to MongoDB Atlas."""
        if not settings.mongo_uri:
            logger.warning("MONGO_URI not configured. Operating in IN-MEMORY database mode.")
            self.is_connected = False
            return False

        try:
            self.client = AsyncIOMotorClient(
                settings.mongo_uri,
                serverSelectionTimeoutMS=5000,
            )
            # Ping database to confirm connection
            await self.client.admin.command("ping")
            self.db = self.client[settings.mongo_db_name]
            self.is_connected = True
            logger.info("Successfully connected to MongoDB Atlas: %s", settings.mongo_db_name)

            # Create essential indexes
            await self.db.users.create_index("user_id", unique=True)
            await self.db.jobs.create_index("job_id", unique=True)
            await self.db.jobs.create_index("status")
            return True
        except Exception as e:
            logger.error("Failed to connect to MongoDB Atlas (%s). Falling back to IN-MEMORY mode.", e)
            self.is_connected = False
            return False

    async def close(self):
        """Close MongoDB connection gracefully."""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("MongoDB Atlas connection closed.")


# Singleton database instance
db_manager = DatabaseManager()
