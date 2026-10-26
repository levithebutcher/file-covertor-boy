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
import rarfile
from bot.utils.progress import ProgressReporter
from bot.utils.file_ops import is_safe_path, format_bytes
from bot.services.queue import queue_manager

logger = logging.getLogger(__name__)


class PasswordRequiredError(Exception):
    """Raised when an archive requires a password for extraction."""
    pass


SUPPORTED_ARCHIVE_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".tgz", ".tar.gz", ".tar.bz2", ".tbz2",
    ".tar.xz", ".txz", ".bz2", ".xz",
    ".cbr", ".cbz",
}

TG_MAX_FILE_SIZE = 2097152000  # 2 GB Telegram ceiling


def is_archive_file(filename: str) -> bool:
    """Check if filename matches known archive formats."""
    lower = filename.lower()
    for ext in SUPPORTED_ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def configure_rarfile_tool():
    """Auto-detect available extraction tool on host system for rarfile."""
    unrar = shutil.which("unrar")
    unar = shutil.which("unar")
    sevenzip = shutil.which("7z") or shutil.which("7zz")
    bsdtar = shutil.which("bsdtar") or shutil.which("tar")

    if unrar:
        rarfile.UNRAR_TOOL = unrar
    if unar:
        rarfile.UNAR_TOOL = unar
    if sevenzip:
        rarfile.SEVENZIP_TOOL = sevenzip
    if bsdtar:
        rarfile.BSDTAR_TOOL = bsdtar

    try:
        rarfile.tool_setup(force=True)
    except Exception as e:
        logger.debug("rarfile tool_setup notice: %s", e)


async def extract_rar_archive(
    archive_path: Path,
    dest_dir: Path,
    password: Optional[str] = None,
) -> bool:
    """
    Robust multi-backend RAR extractor.
    Tries in sequence:
    1. unar CLI (The Unarchiver - handles RAR 1-5 without proprietary dependencies)
    2. unrar CLI (official WinRAR binary if available)
    3. bsdtar / tar CLI (libarchive)
    4. 7z / 7zz CLI
    5. Python rarfile with auto-configured tool
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_str = str(dest_dir.resolve())
    arch_str = str(archive_path.resolve())

    # 1. unar CLI (The Unarchiver - most compatible across all RAR versions)
    unar_bin = shutil.which("unar")
    if unar_bin:
        try:
            cmd = [unar_bin, "-o", dest_str, "-f", "-q"]
            if password:
                cmd.extend(["-p", password])
            cmd.append(arch_str)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
            if "password" in out and any(w in out for w in ("required", "incorrect", "wrong", "enter", "failed")):
                raise PasswordRequiredError("RAR archive is password-protected or password was incorrect.")
            if proc.returncode == 0 and any(dest_dir.rglob("*")):
                logger.info("Successfully extracted RAR using unar CLI.")
                return True
        except PasswordRequiredError:
            raise
        except Exception as e:
            logger.debug("unar CLI error: %s", e)

    # 2. unrar CLI
    unrar_bin = shutil.which("unrar")
    if unrar_bin:
        try:
            cmd = [unrar_bin, "x", "-o+", "-y"]
            if password:
                cmd.append(f"-p{password}")
            else:
                cmd.append("-p-")
            cmd.extend([arch_str, f"{dest_str}/"])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
            if any(w in out for w in ("password", "encrypted", "checksum error in the encrypted file", "corrupt")):
                if "password" in out or "encrypted" in out:
                    raise PasswordRequiredError("RAR archive is password-protected or password was incorrect.")
            if proc.returncode == 0 and any(dest_dir.rglob("*")):
                logger.info("Successfully extracted RAR using unrar CLI.")
                return True
        except PasswordRequiredError:
            raise
        except Exception as e:
            logger.debug("unrar CLI error: %s", e)

    # 3. bsdtar / tar CLI (libarchive)
    tar_bin = shutil.which("bsdtar") or shutil.which("tar")
    if tar_bin:
        try:
            cmd = [tar_bin, "-xf", arch_str, "-C", dest_str]
            if password:
                cmd.extend(["--passphrase", password])
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
            if any(w in out for w in ("passphrase", "encrypted", "password")):
                raise PasswordRequiredError("RAR archive is password-protected or passphrase incorrect.")
            if proc.returncode == 0 and any(dest_dir.rglob("*")):
                logger.info("Successfully extracted RAR using %s.", tar_bin)
                return True
        except PasswordRequiredError:
            raise
        except Exception as e:
            logger.debug("bsdtar/tar error: %s", e)

    # 4. 7z / 7zz CLI
    seven_bin = shutil.which("7z") or shutil.which("7zz")
    if seven_bin:
        try:
            cmd = [seven_bin, "x", f"-o{dest_str}", "-y", "-aot"]
            if password:
                cmd.append(f"-p{password}")
            else:
                cmd.append("-p-")
            cmd.append(arch_str)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
            out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
            if any(w in out for w in ("wrong password", "enter password", "can not open encrypted archive")):
                raise PasswordRequiredError("RAR archive is password-protected or password was incorrect.")
            if proc.returncode == 0 and any(dest_dir.rglob("*")):
                logger.info("Successfully extracted RAR using 7z CLI.")
                return True
        except PasswordRequiredError:
            raise
        except Exception as e:
            logger.debug("7z RAR extraction error: %s", e)

    # 5. rarfile library with auto-configured tool
    try:
        configure_rarfile_tool()
        with rarfile.RarFile(archive_path) as rf:
            if password:
                rf.setpassword(password)
            rf.extractall(dest_dir)
            if any(dest_dir.rglob("*")):
                return True
    except rarfile.PasswordRequired:
        raise PasswordRequiredError("RAR archive is password-protected.")
    except rarfile.BadRarFile as bre:
        if "password" in str(bre).lower():
            raise PasswordRequiredError("RAR archive requires a password.")
        logger.error("rarfile BadRarFile for %s: %s", archive_path.name, bre)
    except Exception as e:
        logger.error("rarfile extraction failed for %s: %s", archive_path.name, e)

    return False


async def fallback_extract(archive_path: Path, dest_dir: Path, password: Optional[str] = None) -> bool:
    """Fallback extractor using zipfile, tarfile, py7zr, bsdtar/tar, unar, or extract_rar_archive."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = archive_path.suffix.lower()
    arch_str = str(archive_path.resolve())
    dest_str = str(dest_dir.resolve())

    try:
        if ext == ".zip":
            # 1. Standard python zipfile
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    pwd = password.encode() if password else None
                    zf.extractall(dest_dir, pwd=pwd)
                    if any(dest_dir.rglob("*")):
                        return True
            except RuntimeError as re:
                if "password" in str(re).lower() or "encrypted" in str(re).lower():
                    raise PasswordRequiredError("Zip archive is password-protected.")
            except Exception as ze:
                logger.debug("Python zipfile failed (%s), attempting bsdtar/unar fallback", ze)

            # 2. bsdtar/tar fallback for zip (handles Deflate64, WinZip AES)
            tar_bin = shutil.which("bsdtar") or shutil.which("tar")
            if tar_bin:
                cmd = [tar_bin, "-xf", arch_str, "-C", dest_str]
                if password:
                    cmd.extend(["--passphrase", password])
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                )
                stdout, stderr = await proc.communicate()
                out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
                if any(w in out for w in ("passphrase", "encrypted", "password")):
                    raise PasswordRequiredError("Zip archive is password-protected.")
                if proc.returncode == 0 and any(dest_dir.rglob("*")):
                    return True

            # 3. unar fallback for zip
            unar_bin = shutil.which("unar")
            if unar_bin:
                cmd = [unar_bin, "-o", dest_str, "-f", "-q"]
                if password:
                    cmd.extend(["-p", password])
                cmd.append(arch_str)
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                )
                stdout, stderr = await proc.communicate()
                out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
                if "password" in out and any(w in out for w in ("required", "incorrect", "wrong", "enter")):
                    raise PasswordRequiredError("Zip archive is password-protected.")
                if proc.returncode == 0 and any(dest_dir.rglob("*")):
                    return True

        elif ext in (".rar", ".cbr"):
            return await extract_rar_archive(archive_path, dest_dir, password)

        elif ext == ".7z":
            # 1. Python py7zr
            try:
                with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
                    archive.extractall(dest_dir)
                    if any(dest_dir.rglob("*")):
                        return True
            except (py7zr.exceptions.PasswordRequired, py7zr.exceptions.Bad7zFile) as pe:
                if "password" in str(pe).lower() or isinstance(pe, py7zr.exceptions.PasswordRequired):
                    raise PasswordRequiredError("7z archive is password-protected.")
                logger.debug("py7zr error on %s: %s", archive_path.name, pe)
            except Exception as e:
                logger.debug("py7zr general error on %s: %s", archive_path.name, e)

            # 2. bsdtar/tar fallback for 7z
            tar_bin = shutil.which("bsdtar") or shutil.which("tar")
            if tar_bin:
                try:
                    cmd = [tar_bin, "-xf", arch_str, "-C", dest_str]
                    if password:
                        cmd.extend(["--passphrase", password])
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdin=asyncio.subprocess.DEVNULL,
                    )
                    stdout, stderr = await proc.communicate()
                    out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
                    if any(w in out for w in ("passphrase", "encrypted", "password")):
                        raise PasswordRequiredError("7z archive is password-protected or passphrase incorrect.")
                    if proc.returncode == 0 and any(dest_dir.rglob("*")):
                        logger.info("Successfully extracted 7z using %s", tar_bin)
                        return True
                except PasswordRequiredError:
                    raise
                except Exception as e:
                    logger.debug("tar 7z error: %s", e)

            # 3. unar fallback for 7z
            unar_bin = shutil.which("unar")
            if unar_bin:
                try:
                    cmd = [unar_bin, "-o", dest_str, "-f", "-q"]
                    if password:
                        cmd.extend(["-p", password])
                    cmd.append(arch_str)
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdin=asyncio.subprocess.DEVNULL,
                    )
                    stdout, stderr = await proc.communicate()
                    out = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).lower()
                    if "password" in out and any(w in out for w in ("required", "incorrect", "wrong", "enter")):
                        raise PasswordRequiredError("7z archive is password-protected.")
                    if proc.returncode == 0 and any(dest_dir.rglob("*")):
                        logger.info("Successfully extracted 7z using unar CLI.")
                        return True
                except PasswordRequiredError:
                    raise
                except Exception as e:
                    logger.debug("unar 7z error: %s", e)

        elif ext in (".tar", ".gz", ".tgz", ".bz2", ".xz") or archive_path.name.lower().endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(dest_dir)
            if any(dest_dir.rglob("*")):
                return True

    except PasswordRequiredError:
        raise
    except Exception as e:
        logger.error("Fallback extraction failed for %s: %s", archive_path.name, e)
    return False


async def extract_archive_7z(
    archive_path: Path,
    dest_dir: Path,
    task_id: str,
    reporter: ProgressReporter,
    password: Optional[str] = None,
) -> bool:
    """
    Extract archive using system 7z binary, unrar, unar, bsdtar, or Python native libraries.
    Handles zip, rar, 7z, tar, gz with security checks and password handling.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_str = str(dest_dir.resolve())
    arch_str = str(archive_path.resolve())
    ext = archive_path.suffix.lower()

    reporter.set_phase("Extracting")

    # 1. RAR / CBR archives route directly to specialized multi-backend RAR extractor
    if ext in (".rar", ".cbr"):
        return await extract_rar_archive(archive_path, dest_dir, password)

    # 2. For .7z, .zip, .tar, .gz: Attempt 7z / 7zz CLI first if available
    seven_bin = shutil.which("7z") or shutil.which("7zz")
    if seven_bin:
        cmd_7z = [
            seven_bin, "x",
            f"-o{dest_str}",
            "-y",
            "-aot",
            "-xr!@PaxHeader",
            "-bsp1",
        ]
        if password:
            cmd_7z.append(f"-p{password}")
        else:
            cmd_7z.append("-p-")  # Prevent 7z from hanging on stdin waiting for password
        cmd_7z.append(arch_str)

        output_lines = []
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_7z,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            await queue_manager.set_process(task_id, proc)

            while True:
                if reporter.is_cancelled:
                    proc.terminate()
                    break
                line = await proc.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                output_lines.append(line_str)
                if "%" in line_str:
                    for part in line_str.split():
                        if part.endswith("%") and part[:-1].isdigit():
                            pct = float(part[:-1])
                            await reporter.update(int(pct), total_bytes=100)
                            break

            stderr_data = await proc.stderr.read()
            await proc.wait()
            combined_output = (" ".join(output_lines) + " " + stderr_data.decode("utf-8", errors="replace")).lower()

            # Check for password indicators in 7z
            if any(w in combined_output for w in ("wrong password", "enter password", "can not open encrypted archive", "password is required")):
                raise PasswordRequiredError("Archive is password-protected or password was incorrect.")

            if proc.returncode == 0 and any(dest_dir.rglob("*")):
                return True

        except PasswordRequiredError:
            raise
        except Exception as e:
            logger.debug("7z CLI execution notice: %s", e)

    # 3. Fallback to specialized libraries and multi-tools (zipfile, py7zr, bsdtar, unar)
    return await fallback_extract(archive_path, dest_dir, password)


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
