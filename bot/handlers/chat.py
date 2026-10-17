"""
Chat and text message handler.
Responds to casual chatter (hi, hello, etc.) with spicy non-veg jokes and guidance,
while gracefully ignoring commands and password replies.
"""

from __future__ import annotations

import re
from hydrogram import Client, filters
from hydrogram.types import Message
from bot.database.users import is_whitelisted, get_user_mode
from bot.utils.jokes import get_random_joke, format_joke_card
from bot.handlers.media import pending_password_archives
from bot.services.zipper import get_staging_stats
from bot.handlers.callbacks import run_zip_package_and_upload


@Client.on_message(filters.text & filters.private, group=2)
async def handle_chat_text(client: Client, message: Message):
    # Ignore slash commands (handled by specific command handlers)
    if not message.text or message.text.startswith("/"):
        return

    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        return

    # If this message is replying to an unzipper password prompt, let the unzipper handler process it!
    if message.reply_to_message and user_id in pending_password_archives:
        if message.reply_to_message.id == pending_password_archives[user_id]["status_msg"].id:
            return

    text_clean = message.text.strip().lower()

    # Check for natural conversational zip triggers (e.g. "create zip", "zip banao", "abb zip create karo", "done", "finish")
    is_zip_phrase = (
        text_clean in ("zip", "done", "finish", "compress", "package")
        or any(phrase in text_clean for phrase in (
            "create zip", "zip create", "make zip", "zip now",
            "zip banao", "zip karo", "zip pack", "pack zip", "start zip"
        ))
    )

    if is_zip_phrase:
        count, _, _ = get_staging_stats(user_id)
        if count > 0:
            status_msg = await message.reply_text(
                f"🗜️ <i>Command received! Bundling all {count} staged files into one .zip archive...</i>"
            )
            await run_zip_package_and_upload(client, message.chat.id, user_id, status_msg)
            return

        mode = await get_user_mode(user_id)
        if mode == "zip":
            await message.reply_text(
                "⚠️ <b>Staging queue is empty!</b>\n"
                "Please send the files or photos you want to bundle first, "
                "then send <b>create zip</b> or tap <b>'Create .ZIP Now'</b>."
            )
            return
        elif any(phrase in text_clean for phrase in ("create zip", "zip create", "make zip", "zip banao", "zip karo")):
            await message.reply_text(
                "ℹ️ <b>Zipper mode is not active.</b>\n"
                "Use /zip or /mode to activate <b>Zipper Mode</b>, then send your files!"
            )
            return

    # Reply with a hilarious nonveg joke for casual text
    joke = get_random_joke()
    await message.reply_text(
        text=format_joke_card(joke),
        disable_web_page_preview=True,
    )
