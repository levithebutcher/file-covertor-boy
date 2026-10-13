"""
Admin and user management handlers (/adduser, /removeuser, /users, /stats).
Restricted exclusively to the bot OWNER_ID and ADMIN_IDS.
"""

from hydrogram import Client, filters
from hydrogram.types import Message
from bot.config import settings
from bot.database.users import is_whitelisted, add_user, remove_user, get_all_users
from bot.templates.cards import access_denied_card


@Client.on_message(filters.command("adduser") & filters.private)
async def handle_adduser(client: Client, message: Message):
    user_id = message.from_user.id
    if not settings.is_admin(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply_text("<b>Usage:</b> <code>/adduser &lt;user_id&gt;</code>")
        return

    target_id = int(parts[1])
    await add_user(target_id, role="whitelisted", added_by=user_id)
    await message.reply_text(f"✅ User <code>{target_id}</code> has been successfully whitelisted.")


@Client.on_message(filters.command("removeuser") & filters.private)
async def handle_removeuser(client: Client, message: Message):
    user_id = message.from_user.id
    if not settings.is_admin(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply_text("<b>Usage:</b> <code>/removeuser &lt;user_id&gt;</code>")
        return

    target_id = int(parts[1])
    success = await remove_user(target_id)
    if success:
        await message.reply_text(f"🗑️ User <code>{target_id}</code> removed from whitelist.")
    else:
        await message.reply_text(f"⚠️ User <code>{target_id}</code> was not found in whitelist.")


@Client.on_message(filters.command("users") & filters.private)
async def handle_list_users(client: Client, message: Message):
    user_id = message.from_user.id
    if not settings.is_admin(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    users = await get_all_users()
    if not users:
        await message.reply_text("📋 <b>Whitelisted Users:</b> None (only admins active).")
        return

    lines = ["📋 <b>Authorized Whitelist:</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for idx, u in enumerate(users, 1):
        uid = u.get("user_id")
        role = u.get("role", "user")
        mode = u.get("mode", "convert")
        lines.append(f"{idx}. <code>{uid}</code> | Role: <b>{role}</b> | Mode: <b>{mode}</b>")

    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("stats") & filters.private)
async def handle_stats(client: Client, message: Message):
    user_id = message.from_user.id
    if not settings.is_admin(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    from bot.services.queue import queue_manager
    users = await get_all_users()
    active_jobs = len(queue_manager.active_tasks)

    stats_msg = (
        "📊 <b>SYSTEM STATUS & TELEMETRY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Primary Owner:</b> <code>{settings.primary_owner_id}</code>\n"
        f"👥 <b>Whitelisted Users:</b> <code>{len(users)}</code>\n"
        f"⚙️ <b>Active Local Tasks:</b> <code>{active_jobs}</code> / <code>{settings.max_concurrent_jobs}</code>\n"
        f"📦 <b>Threshold for Colab:</b> <code>{settings.big_file_threshold_mb} MB</code>\n"
        f"☁️ <b>Host Config:</b> <code>{settings.host_mode}</code>\n"
    )
    await message.reply_text(stats_msg)
