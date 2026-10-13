"""
Archive extraction service.
Extracts .zip, .rar, .7z, .tar, .gz archives, enforces security checks,
detects files > 2 GB, and uploads contents sequentially with rate limiting.
"""

import os
import shutil
import asyncio
import logging
import zipfile
import tarfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import py7zr
from bot.utils.progress import ProgressReporter
from bot.utils.file_ops import is_safe_path, format_bytes
from bot.services.queue import queue_manager

logger = logging.getLogger(__name__)

SUPPORTED_ARCHIVE_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".tgz", ".tar.gz", ".tar.bz2", ".tbz2",
    ".tar.xz", ".txz", ".bz2", ".xz",
}

TG_MAX_FILE_SIZE = 2097152000  # 2 GB Telegram ceiling


def is_archive_file(filename: str) -> bool:
    """Check if filename matches known archive formats."""
    lower = filename.lower()
    for ext in SUPPORTED_ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


async def extract_archive_7z(
    archive_path: Path,
    dest_dir: Path,
    task_id: str,
    reporter: ProgressReporter,
    password: Optional[str] = None,
) -> bool:
    """
    Extract archive using system 7z binary (handles zip, rar, 7z, tar, gz).
    Falls back to Python native extraction if 7z is missing.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_str = str(dest_dir.resolve())
    arch_str = str(archive_path.resolve())

    # Build safe 7z command list (no shell injection)
    cmd = [
        "7z", "x",
        f"-o{dest_str}",
        "-y",
        "-aot",
        "-xr!@PaxHeader",
        "-bsp1",
        arch_str,
    ]
    if password:
        cmd.insert(2, f"-p{password}")

    reporter.set_phase("Extracting")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await queue_manager.set_process(task_id, proc)

        # Stream stdout for progress
        while True:
            if reporter.is_cancelled:
                proc.terminate()
                break
            line = await proc.stdout.readline()
            if not line:
                break
            line_str = line.decode("utf-8", errors="replace").strip()
            if "%" in line_str:
                for part in line_str.split():
                    if part.endswith("%") and part[:-1].isdigit():
                        pct = float(part[:-1])
                        await reporter.update(int(pct), total_bytes=100)
                        break

        await proc.wait()
        if proc.returncode == 0:
            return True

    except FileNotFoundError:
        logger.warning("7z executable not found on system. Attempting Python library fallback.")
    except Exception as e:
        logger.error("Error executing 7z extraction: %s", e)

    # Fallback to Python standard/installed libraries if 7z not available
    return await fallback_extract(archive_path, dest_dir, password)


async def fallback_extract(archive_path: Path, dest_dir: Path, password: Optional[str] = None) -> bool:
    """Fallback extractor using zipfile, tarfile, or py7zr."""
    ext = archive_path.suffix.lower()
    try:
        if ext == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                pwd = password.encode() if password else None
                zf.extractall(dest_dir, pwd=pwd)
            return True
        elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz") or archive_path.name.lower().endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(dest_dir)
            return True
        elif ext == ".7z":
            with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
                archive.extractall(dest_dir)
            return True
    except Exception as e:
        logger.error("Fallback extraction failed for %s: %s", archive_path.name, e)
    return False


def get_and_validate_extracted_files(dest_dir: Path) -> Tuple[List[Path], List[Tuple[str, int]]]:
    """
    Scan extracted directory, filter macOS junk, validate path safety,
    and categorize files into sendable vs oversized (> 2 GB).
    """
    valid_files: List[Path] = []
    oversized_files: List[Tuple[str, int]] = []

    # Clean macOS artifacts
    for root, dirs, files in os.walk(dest_dir):
        if "__MACOSX" in dirs:
            shutil.rmtree(os.path.join(root, "__MACOSX"), ignore_errors=True)
            dirs.remove("__MACOSX")
        for f in files:
            if f in (".DS_Store", "Thumbs.db"):
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass

    # Collect files
    for root, _, files in os.walk(dest_dir):
        for f in sorted(files):
            full_path = Path(root) / f
            # Security: Zip slip check
            if not is_safe_path(dest_dir, full_path):
                logger.warning("Unsafe path traversal detected: %s", full_path)
                continue

            size = full_path.stat().st_size
            if size > TG_MAX_FILE_SIZE:
                oversized_files.append((f, size))
            elif size > 0:
                valid_files.append(full_path)

    return valid_files, oversized_files
