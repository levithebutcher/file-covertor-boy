"""
User access control and per-user operational mode management.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bot.config import settings
from bot.database.mongo import db_manager


async def is_whitelisted(user_id: int) -> bool:
    """Check if a user is the owner, an admin, or in the whitelist."""
    if settings.is_admin(user_id):
        return True

    if db_manager.is_connected and db_manager.db is not None:
        user = await db_manager.db.users.find_one({"user_id": user_id})
        return user is not None
    else:
        return user_id in db_manager._mem_users


async def add_user(user_id: int, role: str = "whitelisted", added_by: int = 0) -> bool:
    """Add a user to the authorized whitelist."""
    doc = {
        "user_id": user_id,
        "role": role,
        "mode": "convert",
        "added_by": added_by,
        "created_at": datetime.now(timezone.utc),
    }

    if db_manager.is_connected and db_manager.db is not None:
        await db_manager.db.users.update_one(
            {"user_id": user_id},
            {"$set": doc},
            upsert=True,
        )
        return True
    else:
        db_manager._mem_users[user_id] = doc
        return True


async def remove_user(user_id: int) -> bool:
    """Remove a user from the authorized whitelist."""
    if db_manager.is_connected and db_manager.db is not None:
        res = await db_manager.db.users.delete_one({"user_id": user_id})
        return res.deleted_count > 0
    else:
        if user_id in db_manager._mem_users:
            del db_manager._mem_users[user_id]
            return True
        return False


async def get_all_users() -> List[Dict[str, Any]]:
    """Return all whitelisted users."""
    if db_manager.is_connected and db_manager.db is not None:
        cursor = db_manager.db.users.find({}, {"_id": 0})
        return await cursor.to_list(length=1000)
    else:
        return list(db_manager._mem_users.values())


async def get_user_mode(user_id: int) -> str:
    """Get the active operational mode for a user (default: 'convert')."""
    if db_manager.is_connected and db_manager.db is not None:
        user = await db_manager.db.users.find_one({"user_id": user_id})
        if user and "mode" in user:
            return user["mode"]
    else:
        if user_id in db_manager._mem_users and "mode" in db_manager._mem_users[user_id]:
            return db_manager._mem_users[user_id]["mode"]
    return "convert"


async def set_user_mode(user_id: int, mode: str) -> bool:
    """Update the active operational mode for a user."""
    if mode not in ("convert", "unzip", "zip"):
        return False

    if db_manager.is_connected and db_manager.db is not None:
        await db_manager.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"mode": mode, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True
    else:
        if user_id not in db_manager._mem_users:
            db_manager._mem_users[user_id] = {"user_id": user_id, "role": "whitelisted"}
        db_manager._mem_users[user_id]["mode"] = mode
        return True
