"""
Unit tests for file operations, filename sanitization, and path safety.
"""

from pathlib import Path
from bot.utils.file_ops import sanitize_filename, is_safe_path
from bot.templates.cards import format_bytes, format_duration, get_progress_bar


def test_sanitize_filename_shell_characters():
    # Remove shell injection characters
    dirty = "my_video; rm -rf / ; $(reboot).mkv"
    cleaned = sanitize_filename(dirty)
    assert ";" not in cleaned
    assert "$" not in cleaned
    assert "(" not in cleaned
    assert ")" not in cleaned
    assert cleaned.endswith(".mkv")


def test_sanitize_filename_directory_traversal():
    # Strip path traversal
    dirty = "../../etc/passwd"
    cleaned = sanitize_filename(dirty)
    assert "/" not in cleaned
    assert ".." not in cleaned
    assert cleaned == "passwd"


def test_sanitize_filename_length_truncation():
    # Preserve extension on long names
    long_name = "a" * 200 + ".mp4"
    cleaned = sanitize_filename(long_name, max_length=100)
    assert len(cleaned) <= 100
    assert cleaned.endswith(".mp4")


def test_is_safe_path_directory_escape():
    base = Path("/app/temp/extracted").resolve()
    safe = base / "folder" / "file.txt"
    unsafe = Path("/app/temp/other_folder/file.txt").resolve()

    assert is_safe_path(base, safe) is True
    assert is_safe_path(base, unsafe) is False


def test_format_bytes():
    assert format_bytes(500) == "500.00 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"


def test_format_duration():
    assert format_duration(45) == "00:45"
    assert format_duration(125) == "02:05"
    assert format_duration(3665) == "01:01:05"


def test_get_progress_bar():
    bar_0 = get_progress_bar(0)
    assert bar_0 == "□□□□□□□□□□"

    bar_50 = get_progress_bar(50)
    assert bar_50 == "■■■■■□□□□□"

    bar_100 = get_progress_bar(100)
    assert bar_100 == "■■■■■■■■■■"
