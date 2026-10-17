"""
Mode switcher handlers and interactive inline keyboard controllers.
Provides instant feedback, live checkmark toggles, and direct slash commands.
"""

from __future__ import annotations

from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery
from bot.database.users import is_whitelisted, get_user_mode, set_user_mode
from bot.services.zipper import get_staging_stats
from bot.templates.cards import start_card, mode_card, access_denied_card, zipper_staging_card
from bot.templates.buttons import mode_keyboard, zipper_actions_keyboard


@Client.on_message(filters.command("start") & filters.private)
async def handle_start(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Friend"
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id, user_name))
        return

    current_mode = await get_user_mode(user_id)

    await message.reply_text(
        text=start_card(user_name, user_id, current_mode.upper()),
        reply_markup=mode_keyboard(current_mode),
    )


@Client.on_message(filters.command("mode") & filters.private)
async def handle_mode(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Friend"
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id, user_name))
        return

    user_name = message.from_user.first_name or "User"
    current_mode = await get_user_mode(user_id)

    await message.reply_text(
        text=mode_card(user_name, user_id, current_mode),
        reply_markup=mode_keyboard(current_mode),
    )


@Client.on_message(filters.command("convert") & filters.private)
async def handle_shortcut_convert(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    await set_user_mode(user_id, "convert")
    await message.reply_text("🎬 <b>Switched to Video Converter Mode!</b>\nSend any video file to convert to MP4.")


@Client.on_message(filters.command("unzip") & filters.private)
async def handle_shortcut_unzip(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    await set_user_mode(user_id, "unzip")
    await message.reply_text("📦 <b>Switched to Unzipper Mode!</b>\nSend any archive (.zip, .rar, .7z, .tar, .gz) to extract.")


@Client.on_message(filters.command("zip") & filters.private)
async def handle_shortcut_zip(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    await set_user_mode(user_id, "zip")
    count, total_staged, latest = get_staging_stats(user_id)
    if count > 0:
        await message.reply_text(
            text=zipper_staging_card(count, total_staged, latest),
            reply_markup=zipper_actions_keyboard(),
        )
    else:
        await message.reply_text(
            "🗜️ <b>Switched to Zipper Mode!</b>\n\n"
            "• Send any files, photos, videos, or documents to add to your zip batch.\n"
            "• When finished, tap <b>'Create .ZIP Now'</b> or send <code>/finish</code>.\n"
            "• To clear your batch, send <code>/clear</code>."
        )


@Client.on_callback_query(filters.regex(r"^set_mode:(convert|unzip|zip)$"))
async def handle_mode_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_whitelisted(user_id):
        await callback.answer("Access restricted.", show_alert=True)
        return

    new_mode = callback.matches[0].group(1)
    await set_user_mode(user_id, new_mode)

    mode_labels = {
        "convert": "🎬 Video Converter",
        "unzip": "📦 Unzipper",
        "zip": "🗜️ Zipper",
    }
    label = mode_labels.get(new_mode, new_mode)

    # Toast feedback
    await callback.answer(f"Switched to {label}!", show_alert=False)

    # Dynamically update message in-place
    user_name = callback.from_user.first_name or "User"
    await callback.message.edit_text(
        text=mode_card(user_name, user_id, new_mode),
        reply_markup=mode_keyboard(new_mode),
    )
