"""
Visual UI cards and glassmorphic layout formatting for Telegram messages.
"""

from typing import Optional


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string (KiB, MiB, GiB)."""
    if not size or size < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    s = float(size)
    while s >= 1024.0 and unit_idx < len(units) - 1:
        s /= 1024.0
        unit_idx += 1
    return f"{s:.2f} {units[unit_idx]}"


def format_duration(seconds: float) -> str:
    """Format duration into human readable string."""
    seconds = int(seconds)
    if seconds < 0:
        return "--:--"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_progress_bar(percentage: float, length: int = 10) -> str:
    """Return a visual progress bar e.g. ■■■■■□□□□□."""
    percentage = max(0.0, min(100.0, percentage))
    filled_count = int(round((percentage / 100.0) * length))
    empty_count = length - filled_count
    return "■" * filled_count + "□" * empty_count


def start_card(user_name: str, user_id: int, mode_name: str, host: str = "Render") -> str:
    """Welcome card displayed on /start."""
    return (
        "╔════════════════════════════════════╗\n"
        "║     ✨ NEXUS MEDIA SUITE | v1.0    ║\n"
        "╚════════════════════════════════════╝\n"
        f"👤 <b>User:</b> {user_name} (<code>{user_id}</code>)\n"
        f"🎯 <b>Active Mode:</b> {mode_name}\n"
        f"☁️ <b>Host Node:</b> 🟢 {host}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome to your private media automation suite!\n\n"
        "<b>Available Features:</b>\n"
        "• 🎬 <b>Video Converter:</b> Convert any video to streamable MP4\n"
        "• 📦 <b>Unzipper:</b> Extract zip, rar, 7z, tar, gz archives\n"
        "• 🗜️ <b>Zipper:</b> Bundle multiple files into a single archive\n\n"
        "<i>Use /mode or the buttons below to switch your active mode anytime.</i>"
    )


def mode_card(user_name: str, user_id: int, current_mode: str, host: str = "Render") -> str:
    """Dashboard card displayed on /mode."""
    mode_titles = {
        "convert": "🎬 Video Converter (MP4)",
        "unzip": "📦 Unzipper (Archive Extractor)",
        "zip": "🗜️ Zipper (Multi-File Bundler)",
    }
    mode_desc = {
        "convert": "Send any video file (MKV, AVI, WEBM, FLV, TS, etc.) to convert to high-quality streaming MP4.",
        "unzip": "Send any archive (.zip, .rar, .7z, .tar, .gz) to extract and receive all contents sequentially.",
        "zip": "Send multiple files to bundle them into a single archive. Max 2 GB per part.",
    }
    title = mode_titles.get(current_mode, current_mode.upper())
    desc = mode_desc.get(current_mode, "Ready to process files.")

    return (
        "╔════════════════════════════════════╗\n"
        "║      ⚙️ MODE CONTROL CENTER        ║\n"
        "╚════════════════════════════════════╝\n"
        f"👤 <b>User:</b> {user_name} (<code>{user_id}</code>)\n"
        f"🎯 <b>Active Mode:</b> {title}\n"
        f"☁️ <b>Active Node:</b> 🟢 {host}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Current Workflow:</b>\n{desc}\n\n"
        "<i>Select a mode below to switch instantly:</i>"
    )


def progress_card(
    task_name: str,
    phase: str,
    current_bytes: int,
    total_bytes: int,
    speed_bytes_sec: float,
    eta_seconds: float,
    percentage: float,
) -> str:
    """Real-time live progress card with visual bar, speed, and ETA."""
    p_bar = get_progress_bar(percentage)
    current_str = format_bytes(current_bytes)
    total_str = format_bytes(total_bytes) if total_bytes > 0 else "Unknown"
    speed_str = f"{format_bytes(int(speed_bytes_sec))}/s"
    eta_str = format_duration(eta_seconds)

    phase_emojis = {
        "Downloading": "📥",
        "Converting": "⚙️",
        "Extracting": "📦",
        "Zipping": "🗜️",
        "Uploading": "📤",
    }
    emoji = phase_emojis.get(phase, "⚡")

    return (
        f"<b>{emoji} {phase.upper()}...</b>\n"
        f"<code>{task_name}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Progress:</b> <code>[{p_bar}]</code> {percentage:.1f}%\n"
        f"<b>Transferred:</b> <code>{current_str}</code> / <code>{total_str}</code>\n"
        f"<b>Speed:</b> <code>{speed_str}</code> | <b>ETA:</b> <code>{eta_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Press Cancel below to abort task immediately.</i>"
    )


def large_file_card(file_name: str, file_size: int, threshold_mb: int) -> str:
    """Alert card when file exceeds Render Free memory/disk threshold."""
    size_str = format_bytes(file_size)
    return (
        "⚠️ <b>LARGE FILE DETECTED — OVERFLOW QUEUE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>File:</b> <code>{file_name}</code>\n"
        f"📊 <b>Size:</b> <code>{size_str}</code> (Limit: <code>{threshold_mb} MB</code>)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Due to Render Free tier memory & disk limits (512 MB RAM),\n"
        "this job has been <b>safely saved</b> for Colab execution.\n\n"
        "👉 <b>Action Required:</b>\n"
        "Open your Google Colab notebook and click <b>'Run All'</b>.\n"
        "The Colab worker will automatically claim this job, process it, "
        "and send the result directly to your chat!"
    )


def access_denied_card(user_id: int) -> str:
    """Polite denial message for unauthorized users."""
    return (
        "🔒 <b>ACCESS RESTRICTED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "This bot is currently private and restricted to the bot owner "
        "and authorized whitelisted users.\n\n"
        f"Your Telegram ID: <code>{user_id}</code>\n\n"
        "<i>Please contact the bot administrator to request access.</i>"
    )


def zipper_staging_card(file_count: int, total_size: int, latest_file: str) -> str:
    """Status card for active zipper batch."""
    size_str = format_bytes(total_size)
    return (
        "🗜️ <b>ZIP BATCH IN PROGRESS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 <b>Queued Files:</b> <code>{file_count}</code>\n"
        f"📦 <b>Total Staged Size:</b> <code>{size_str}</code>\n"
        f"📄 <b>Latest Added:</b> <code>{latest_file}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send more files to add to this archive, or tap\n"
        "<b>'Create .ZIP Now'</b> to build and upload the package.\n\n"
        "<i>(Files > 2 GB will automatically be split into volumes)</i>"
    )
