"""
User access control and per-user operational mode management using local SQLite.
Zero network latency, 100% reliable.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bot.config import settings
from bot.database.db import db_manager


async def is_whitelisted(user_id: int) -> bool:
    """Check if a user is the owner, an admin, or in the whitelist."""
    if settings.is_admin(user_id):
        return True

    row = await db_manager.fetchone(
        "SELECT user_id FROM users WHERE user_id = ?;",
        (user_id,)
    )
    return row is not None


async def add_user(user_id: int, role: str = "whitelisted", added_by: int = 0) -> bool:
    """Add a user to the authorized whitelist."""
    now_str = datetime.now(timezone.utc).isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (user_id, role, mode, added_by, created_at, updated_at)
        VALUES (?, ?, 'convert', ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            role = excluded.role,
            added_by = excluded.added_by,
            updated_at = excluded.updated_at;
        """,
        (user_id, role, added_by, now_str, now_str)
    )
    return True


async def remove_user(user_id: int) -> bool:
    """Remove a user from the authorized whitelist."""
    count = await db_manager.execute(
        "DELETE FROM users WHERE user_id = ?;",
        (user_id,)
    )
    return count > 0


async def get_all_users() -> List[Dict[str, Any]]:
    """Return all whitelisted users."""
    return await db_manager.fetchall("SELECT * FROM users ORDER BY created_at ASC;")


async def get_user_mode(user_id: int) -> str:
    """Get the active operational mode for a user (default: 'convert')."""
    row = await db_manager.fetchone(
        "SELECT mode FROM users WHERE user_id = ?;",
        (user_id,)
    )
    if row and row.get("mode"):
        return row["mode"]
    return "convert"


async def set_user_mode(user_id: int, mode: str) -> bool:
    """Update the active operational mode for a user."""
    if mode not in ("convert", "unzip", "zip"):
        return False

    now_str = datetime.now(timezone.utc).isoformat()
    await db_manager.execute(
        """
        INSERT INTO users (user_id, role, mode, added_by, created_at, updated_at)
        VALUES (?, 'whitelisted', ?, 0, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            mode = excluded.mode,
            updated_at = excluded.updated_at;
        """,
        (user_id, mode, now_str, now_str)
    )
    return True
