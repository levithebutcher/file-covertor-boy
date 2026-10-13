"""
Unit tests for distributed host locking, heartbeat, and handoff transitions.
"""

import pytest
from bot.database.jobs import (
    acquire_host_lock,
    heartbeat_host_lock,
    release_host_lock,
    get_lock_state,
    create_pending_job,
    get_pending_jobs,
    update_job_status,
)


@pytest.mark.asyncio
async def test_handoff_lock_lifecycle():
    # 1. Render acquires lock
    res = await acquire_host_lock("render")
    assert res is True
    state = await get_lock_state()
    assert state.get("active_host") == "render"

    # 2. Heartbeat keeps it alive
    hb = await heartbeat_host_lock("render")
    assert hb is True

    # 3. Colab claims lock
    colab_res = await acquire_host_lock("colab", ttl_seconds=0)
    assert colab_res is True
    state = await get_lock_state()
    assert state.get("active_host") == "colab"

    # 4. Colab releases lock back to Render
    rel = await release_host_lock("colab")
    assert rel is True
    state = await get_lock_state()
    assert state.get("active_host") == "render"


@pytest.mark.asyncio
async def test_pending_job_queue():
    # Create large file job
    job_id = await create_pending_job(
        chat_id=12345,
        message_id=999,
        file_id="tg_file_abc",
        file_name="movie_2gb.mkv",
        file_size=1500000000,
        mode="convert",
    )
    assert len(job_id) == 8

    # Query pending jobs
    pending = await get_pending_jobs()
    matching = [j for j in pending if j["job_id"] == job_id]
    assert len(matching) == 1
    assert matching[0]["file_name"] == "movie_2gb.mkv"
    assert matching[0]["status"] == "pending_colab"

    # Update job state
    up = await update_job_status(job_id, "completed")
    assert up is True

    # Job is no longer pending
    pending_after = await get_pending_jobs()
    matching_after = [j for j in pending_after if j["job_id"] == job_id]
    assert len(matching_after) == 0
