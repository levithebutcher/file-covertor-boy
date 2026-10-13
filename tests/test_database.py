"""
Unit tests for local SQLite user whitelist and operational mode storage.
"""

import pytest
from bot.database.users import is_whitelisted, add_user, remove_user, get_all_users, get_user_mode, set_user_mode


@pytest.mark.asyncio
async def test_sqlite_user_whitelist_lifecycle():
    test_uid = 999111222

    # Initially not whitelisted
    assert await is_whitelisted(test_uid) is False

    # Add user
    added = await add_user(test_uid, role="vip", added_by=123)
    assert added is True
    assert await is_whitelisted(test_uid) is True

    # Check in get_all_users
    users = await get_all_users()
    matched = [u for u in users if u["user_id"] == test_uid]
    assert len(matched) == 1
    assert matched[0]["role"] == "vip"

    # Remove user
    removed = await remove_user(test_uid)
    assert removed is True
    assert await is_whitelisted(test_uid) is False


@pytest.mark.asyncio
async def test_sqlite_user_mode_switching():
    test_uid = 888222333

    # Default mode is convert
    mode = await get_user_mode(test_uid)
    assert mode == "convert"

    # Switch to unzip
    ok = await set_user_mode(test_uid, "unzip")
    assert ok is True
    assert await get_user_mode(test_uid) == "unzip"

    # Switch to zip
    ok = await set_user_mode(test_uid, "zip")
    assert ok is True
    assert await get_user_mode(test_uid) == "zip"

    # Invalid mode returns False and does not change
    ok = await set_user_mode(test_uid, "invalid_mode")
    assert ok is False
    assert await get_user_mode(test_uid) == "zip"

    # Cleanup
    await remove_user(test_uid)
