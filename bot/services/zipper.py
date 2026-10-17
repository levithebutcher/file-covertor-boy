from __future__ import annotations

import os
import shutil
import asyncio
import logging
import zipfile
from pathlib import Path
from typing import List, Tuple, Dict, Any

from bot.utils.file_ops import sanitize_filename, safe_remove_dir, is_safe_path
from bot.utils.progress import ProgressReporter
from bot.services.queue import queue_manager

logger = logging.getLogger(__name__)

ZIPPER_STAGING_BASE = Path("temp/zipper_staging")
TG_SPLIT_VOLUME_BYTES = 1900 * 1024 * 1024  # 1.9 GB chunk target for Telegram safe upload


def get_user_staging_dir(user_id: int) -> Path:
    """Return the active staging directory for a user's zip batch."""
    staging_dir = ZIPPER_STAGING_BASE / str(user_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir


def get_staging_stats(user_id: int) -> Tuple[int, int, str]:
    """Return (count, total_size_bytes, latest_file_name)."""
    staging_dir = get_user_staging_dir(user_id)
    files = [f for f in staging_dir.iterdir() if f.is_file()]
    total_size = sum(f.stat().st_size for f in files)
    latest_file = files[-1].name if files else "None"
    return len(files), total_size, latest_file


def get_staging_files_info(user_id: int) -> Tuple[int, int, List[Tuple[str, int]]]:
    """Return (count, total_size_bytes, [(filename, file_size), ...])."""
    staging_dir = get_user_staging_dir(user_id)
    files = sorted([f for f in staging_dir.iterdir() if f.is_file()], key=lambda f: f.stat().st_mtime)
    total_size = sum(f.stat().st_size for f in files)
    file_info = [(f.name, f.stat().st_size) for f in files]
    return len(files), total_size, file_info


def clear_staging(user_id: int) -> None:
    """Clear all staged files for a user."""
    staging_dir = get_user_staging_dir(user_id)
    safe_remove_dir(staging_dir)


async def add_file_to_staging(
    user_id: int,
    source_file: Path,
    original_filename: str,
) -> Tuple[int, int, str]:
    """Move or copy a downloaded file into the user's zip staging directory."""
    staging_dir = get_user_staging_dir(user_id)
    clean_name = sanitize_filename(original_filename)

    # Avoid duplicate name collision
    target_path = staging_dir / clean_name
    counter = 1
    while target_path.exists():
        stem, ext = os.path.splitext(clean_name)
        target_path = staging_dir / f"{stem}_{counter}{ext}"
        counter += 1

    shutil.move(str(source_file), str(target_path))
    return get_staging_stats(user_id)


async def create_zip_package(
    user_id: int,
    task_id: str,
    output_dir: Path,
    reporter: ProgressReporter,
    base_archive_name: str = "archive.zip",
) -> List[Path]:
    """
    Compress all files in the staging directory into .zip.
    If archive exceeds 2 GB, splits into volumes (.zip.001, .zip.002, etc.).
    Returns list of output archive paths.
    """
    staging_dir = get_user_staging_dir(user_id)
    staged_files = [f for f in staging_dir.iterdir() if f.is_file()]
    if not staged_files:
        return []

    total_staged_size = sum(f.stat().st_size for f in staged_files)
    reporter.set_phase("Zipping", total_bytes=total_staged_size)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if 7z is available for high-speed multi-volume compression
    out_archive = output_dir / base_archive_name

    if total_staged_size >= TG_SPLIT_VOLUME_BYTES:
        logger.info("Total size (%d bytes) exceeds 1.9 GB. Creating multi-part split archive.", total_staged_size)
        cmd = [
            "7z", "a",
            f"-v1900m",
            str(out_archive.resolve()),
            str(staging_dir.resolve()) + "/*",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await queue_manager.set_process(task_id, proc)
            await proc.communicate()
            if proc.returncode == 0:
                parts = sorted(output_dir.glob(f"{base_archive_name}.*"))
                if parts:
                    return parts
        except FileNotFoundError:
            logger.warning("7z not found for volume split. Falling back to single zip.")

    # Standard single zip creation
    try:
        with zipfile.ZipFile(out_archive, "w", zipfile.ZIP_DEFLATED) as zf:
            processed = 0
            for file_path in staged_files:
                if reporter.is_cancelled:
                    return []
                zf.write(file_path, arcname=file_path.name)
                processed += file_path.stat().st_size
                await reporter.update(processed, total_bytes=total_staged_size)

        if out_archive.exists() and out_archive.stat().st_size > 0:
            return [out_archive]
    except Exception as e:
        logger.error("Failed to build zip package: %s", e)

    return []
