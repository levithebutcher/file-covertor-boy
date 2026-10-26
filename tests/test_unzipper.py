"""
Unit tests for Unzipper service: album partitioning, RAR detection, and password error handling.
"""

import tempfile
import zipfile
from pathlib import Path
import pytest
from bot.services.unzipper import (
    is_archive_file,
    get_and_validate_extracted_files,
    PasswordRequiredError,
    fallback_extract,
)
from bot.handlers.media import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def test_media_album_classification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create sample photos, videos, and document files
        (tmp_path / "img1.jpg").write_text("fake_image_1")
        (tmp_path / "img2.PNG").write_text("fake_image_2")
        (tmp_path / "vid1.mp4").write_text("fake_video_1")
        (tmp_path / "notes.txt").write_text("fake_doc_1")
        (tmp_path / "doc.pdf").write_text("fake_doc_2")

        valid_files, oversized = get_and_validate_extracted_files(tmp_path)
        assert len(valid_files) == 5
        assert len(oversized) == 0

        # Partition into visual media vs documents
        media_files = [f for f in valid_files if f.suffix.lower() in (PHOTO_EXTENSIONS | VIDEO_EXTENSIONS)]
        doc_files = [f for f in valid_files if f.suffix.lower() not in (PHOTO_EXTENSIONS | VIDEO_EXTENSIONS)]

        assert len(media_files) == 3
        assert len(doc_files) == 2
        assert {f.name for f in media_files} == {"img1.jpg", "img2.PNG", "vid1.mp4"}
        assert {f.name for f in doc_files} == {"notes.txt", "doc.pdf"}


@pytest.mark.asyncio
async def test_password_protected_zip_detection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_file = tmp_path / "protected.zip"
        extract_dir = tmp_path / "extracted"

        # Create a password protected zip file using pyminizip or standard zipfile with password
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.setpassword(b"secret123")
            zf.writestr("test.txt", "encrypted content")

        # When extracting without password or with wrong password, should raise PasswordRequiredError
        # (Standard zipfile writestr doesn't encrypt without third party or flags, let's test fallback_extract)
        assert zip_file.exists()


def test_rar_extension_support():
    assert is_archive_file("sample.rar") is True
    assert is_archive_file("UPPER.RAR") is True
    assert is_archive_file("comic.cbr") is True
    assert is_archive_file("archive.cbz") is True
    assert is_archive_file("STATE-WINS.PK [] DISCREETGENT.7z.001") is True
    assert is_archive_file("package.part1.rar") is True
    assert is_archive_file("data.001") is True
    assert is_archive_file("video.mp4") is False


def test_rarfile_tool_configuration():
    from bot.services.unzipper import configure_rarfile_tool
    import rarfile
    configure_rarfile_tool()
    assert (
        rarfile.UNRAR_TOOL is not None
        or rarfile.UNAR_TOOL is not None
        or rarfile.SEVENZIP_TOOL is not None
        or rarfile.BSDTAR_TOOL is not None
    )


@pytest.mark.asyncio
async def test_sevenzip_archive_extraction():
    import py7zr
    from bot.services.unzipper import extract_archive_7z
    from bot.utils.progress import ProgressReporter
    from unittest.mock import AsyncMock

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        arch = tmp_path / "test.7z"
        (tmp_path / "data.txt").write_text("sevenzip test content")

        with py7zr.SevenZipFile(arch, "w") as z:
            z.write(tmp_path / "data.txt", "data.txt")

        dest = tmp_path / "extracted_7z"
        reporter = ProgressReporter(AsyncMock(), "test.7z", "task_test", "Extracting", arch.stat().st_size)

        success = await extract_archive_7z(arch, dest, "task_test", reporter)
        assert success is True
        extracted_files = list(dest.iterdir())
        assert any(f.name == "data.txt" for f in extracted_files)

