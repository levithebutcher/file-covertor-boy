"""
Job queueing and distributed host-locking for Render and Google Colab coordination.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import uuid
from bot.database.mongo import db_manager


async def create_pending_job(
    chat_id: int,
    message_id: int,
    file_id: str,
    file_name: str,
    file_size: int,
    mode: str,
) -> str:
    """Create and queue a large file job for Colab overflow processing."""
    job_id = str(uuid.uuid4())[:8]
    doc = {
        "job_id": job_id,
        "chat_id": chat_id,
        "message_id": message_id,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "mode": mode,
        "status": "pending_colab",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    if db_manager.is_connected and db_manager.db is not None:
        await db_manager.db.jobs.insert_one(doc)
    else:
        db_manager._mem_jobs[job_id] = doc

    return job_id


async def get_pending_jobs() -> List[Dict[str, Any]]:
    """Retrieve all jobs waiting for Colab execution."""
    if db_manager.is_connected and db_manager.db is not None:
        cursor = db_manager.db.jobs.find(
            {"status": "pending_colab"},
            {"_id": 0}
        ).sort("created_at", 1)
        return await cursor.to_list(length=100)
    else:
        return [
            j for j in db_manager._mem_jobs.values()
            if j.get("status") == "pending_colab"
        ]


async def update_job_status(job_id: str, status: str, error: Optional[str] = None) -> bool:
    """Update job state (processing, completed, failed)."""
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc),
    }
    if error:
        update_data["error"] = error

    if db_manager.is_connected and db_manager.db is not None:
        res = await db_manager.db.jobs.update_one(
            {"job_id": job_id},
            {"$set": update_data}
        )
        return res.modified_count > 0
    else:
        if job_id in db_manager._mem_jobs:
            db_manager._mem_jobs[job_id].update(update_data)
            return True
        return False


# ==============================================================================
# DISTRIBUTED HOST LOCK (Render <-> Colab Coordination)
# ==============================================================================

LOCK_ID = "master_host_lock"


async def get_lock_state() -> Dict[str, Any]:
    """Get current active host and heartbeat status."""
    now = datetime.now(timezone.utc)
    if db_manager.is_connected and db_manager.db is not None:
        doc = await db_manager.db.handoff_lock.find_one({"_id": LOCK_ID})
        if not doc:
            # Initialize lock with default 'render'
            initial = {
                "_id": LOCK_ID,
                "active_host": "render",
                "heartbeat": now,
                "colab_waiting": False,
            }
            await db_manager.db.handoff_lock.insert_one(initial)
            return initial
        return doc
    else:
        return db_manager._mem_lock


async def acquire_host_lock(host: str, ttl_seconds: int = 45) -> bool:
    """
    Attempt to claim the master host lock.
    Host can acquire if:
    1. Lock is owned by host, OR
    2. Heartbeat of previous owner is older than ttl_seconds (stale failover).
    """
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(seconds=ttl_seconds)

    if db_manager.is_connected and db_manager.db is not None:
        # Atomic find_one_and_update
        res = await db_manager.db.handoff_lock.find_one_and_update(
            {
                "_id": LOCK_ID,
                "$or": [
                    {"active_host": host},
                    {"heartbeat": {"$lt": stale_threshold}},
                ],
            },
            {
                "$set": {
                    "active_host": host,
                    "heartbeat": now,
                    "colab_waiting": (host == "colab"),
                }
            },
            upsert=True,
            return_document=True,
        )
        return res is not None and res.get("active_host") == host
    else:
        current = db_manager._mem_lock
        last_hb = current.get("heartbeat", now)
        if current.get("active_host") == host or (now - last_hb).total_seconds() > ttl_seconds:
            db_manager._mem_lock["active_host"] = host
            db_manager._mem_lock["heartbeat"] = now
            return True
        return False


async def heartbeat_host_lock(host: str) -> bool:
    """Send periodic heartbeat to keep the host lock alive."""
    now = datetime.now(timezone.utc)
    if db_manager.is_connected and db_manager.db is not None:
        res = await db_manager.db.handoff_lock.update_one(
            {"_id": LOCK_ID, "active_host": host},
            {"$set": {"heartbeat": now}}
        )
        return res.modified_count > 0
    else:
        if db_manager._mem_lock.get("active_host") == host:
            db_manager._mem_lock["heartbeat"] = now
            return True
        return False


async def release_host_lock(host: str) -> bool:
    """Release lock and return control back to Render."""
    now = datetime.now(timezone.utc)
    if db_manager.is_connected and db_manager.db is not None:
        await db_manager.db.handoff_lock.update_one(
            {"_id": LOCK_ID, "active_host": host},
            {"$set": {"active_host": "render", "heartbeat": now, "colab_waiting": False}}
        )
        return True
    else:
        if db_manager._mem_lock.get("active_host") == host:
            db_manager._mem_lock["active_host"] = "render"
            db_manager._mem_lock["heartbeat"] = now
            return True
        return False
