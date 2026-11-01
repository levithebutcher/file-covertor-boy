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
    await message.reply_text(
        "📦 <b>Switched to Unzipper Mode!</b>\n"
        "• Send any archive (.zip, .rar, .7z, .tar, .gz, .cbr) to extract.\n"
        "• Send direct public web links (URLs) to extract without Telegram file limits.\n"
        "• Send multi-part split volumes (.001, .part1.rar) to gather and unpack together!"
    )


from bot.services.unzipper import get_unzip_staging_info
from bot.templates.cards import unzip_split_staging_card
from bot.templates.buttons import unzip_staging_actions_keyboard


@Client.on_message(filters.command(["merge", "parts"]) & filters.private)
async def handle_cmd_merge(client: Client, message: Message):
    user_id = message.from_user.id
    if not await is_whitelisted(user_id):
        await message.reply_text(access_denied_card(user_id))
        return

    await set_user_mode(user_id, "unzip")
    count, total_staged, file_info = get_unzip_staging_info(user_id)
    if count > 0:
        await message.reply_text(
            text=unzip_split_staging_card(count, total_staged, file_info),
            reply_markup=unzip_staging_actions_keyboard(count),
        )
    else:
        await message.reply_text(
            "🧩 <b>Split Archive Collector Active!</b>\n\n"
            "• Send your multi-part archive volumes one by one (e.g. <code>.7z.001</code>, <code>.7z.002</code>, or <code>.part1.rar</code>, <code>.part2.rar</code>).\n"
            "• When all parts are sent, tap <b>'🚀 Extract All Parts Now'</b> (or send <code>/done</code>) to unpack the complete archive!"
        )


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
