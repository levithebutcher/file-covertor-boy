"""
Inline keyboard builders for interactive UI components.
"""

from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """
    Builds the interactive mode switcher keyboard.
    Highlights current mode with a checkmark badge.
    """
    modes = [
        ("convert", "🎬 Video Converter"),
        ("unzip", "📦 Unzipper"),
        ("zip", "🗜️ Zipper"),
    ]

    buttons = []
    row = []
    for mode_key, label in modes:
        badge = " ✅" if mode_key == current_mode else ""
        button_text = f"{label}{badge}"
        row.append(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"set_mode:{mode_key}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Control and utility buttons
    buttons.append([
        InlineKeyboardButton("ℹ️ Mode Info", callback_data="mode_info"),
        InlineKeyboardButton("❌ Close Menu", callback_data="close_menu"),
    ])

    return InlineKeyboardMarkup(buttons)


def progress_cancel_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Cancel button attached to active live progress cards."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Task", callback_data=f"cancel_task:{task_id}")]
    ])


def zipper_actions_keyboard() -> InlineKeyboardMarkup:
    """Action buttons for Zipper staging batches."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Create .ZIP Now", callback_data="zip_finish"),
            InlineKeyboardButton("🗑️ Clear Batch", callback_data="zip_clear"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_menu"),
        ]
    ])


def close_keyboard() -> InlineKeyboardMarkup:
    """Simple close button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
    ])
