"""
Safe file and disk operations, including filename sanitization and disk safety checks.
"""

import os
import re
import shutil
import unicodedata
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from bot.templates.cards import format_bytes, format_duration

# Base temporary storage directory
TEMP_BASE_DIR = Path("temp")


def sanitize_filename(filename: str, max_length: int = 150) -> str:
    """
    Sanitize an untrusted user filename to prevent shell injection,
    directory traversal (e.g., ../), and invalid filesystem characters.
    """
    if not filename:
        return "unnamed_file"

    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)

    # Strip directory components (prevent path traversal)
    filename = os.path.basename(filename)

    # Replace forbidden shell and filesystem characters with underscore
    # Forbidden: \ / : * ? " < > | ; & $ ` { } ( ) ! ' \n \r \t
    cleaned = re.sub(r'[\/\\:\*\?"<>\|;&$`\{\}\(\)!\'\n\r\t]', "_", filename)

    # Replace multiple spaces/underscores
    cleaned = re.sub(r"[_\s]+", "_", cleaned).strip(" ._")

    # If filename is empty after stripping, provide fallback
    if not cleaned:
        cleaned = "processed_file"

    # Truncate length while preserving file extension
    if len(cleaned) > max_length:
        stem, ext = os.path.splitext(cleaned)
        max_stem_len = max(1, max_length - len(ext))
        cleaned = stem[:max_stem_len] + ext

    return cleaned


def has_enough_free_space(required_bytes: int, path: str = ".", margin_ratio: float = 1.25) -> bool:
    """
    Check if the host filesystem has enough free disk space.
    Adds a safety margin (default 25%) to avoid disk full crashes on Render.
    """
    try:
        usage = shutil.disk_usage(path)
        needed = int(required_bytes * margin_ratio)
        has_space = usage.free >= needed
        if not has_space:
            logger.warning(
                "Insufficient disk space at %s: Required %d bytes (with margin), Free %d bytes",
                path, needed, usage.free
            )
        return has_space
    except Exception as e:
        logger.error("Failed to check disk usage: %s", e)
        return True  # If check fails, do not block operation


def get_task_dir(user_id: int, task_id: str) -> Path:
    """Create and return an isolated temporary directory for a specific task."""
    task_dir = TEMP_BASE_DIR / str(user_id) / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def safe_remove_dir(path: Path | str) -> None:
    """Safely remove a directory and all its contents without throwing exceptions."""
    try:
        p = Path(path)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            logger.debug("Successfully cleaned directory: %s", p)
    except Exception as e:
        logger.warning("Error cleaning directory %s: %s", path, e)


def is_safe_path(base_dir: Path | str, target_path: Path | str) -> bool:
    """Verify that a path does not escape base_dir (Zip slip / directory traversal defense)."""
    try:
        base = Path(base_dir).resolve()
        target = Path(target_path).resolve()
        return base in target.parents or base == target
    except Exception:
        return False
