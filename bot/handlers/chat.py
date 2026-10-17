"""
Chat and text message handler.
Responds to casual chatter (hi, hello, etc.) with spicy non-veg jokes and guidance,
while gracefully ignoring commands and password replies.
"""

from __future__ import annotations

from hydrogram import Client, filters
from hydrogram.types import Message
from bot.database.users import is_whitelisted
from bot.utils.jokes import get_random_joke, format_joke_card
from bot.handlers.media import pending_password_archives


@Client.on_message(filters.text & filters.private, group=2)
async def handle_chat_text(client: Client, message: Message):
    # Ignore commands (handled by specific command handlers)
    if not message.text or message.text.startswith("/"):
        return

    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        return

    # If this message is replying to an unzipper password prompt, let the unzipper handler process it!
    if message.reply_to_message and user_id in pending_password_archives:
        if message.reply_to_message.id == pending_password_archives[user_id]["status_msg"].id:
            return

    # Reply with a hilarious nonveg joke
    joke = get_random_joke()
    await message.reply_text(
        text=format_joke_card(joke),
        disable_web_page_preview=True,
    )
