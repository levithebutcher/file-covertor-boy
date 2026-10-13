"""
Unit tests for media format detection and routing filters.
"""

from bot.services.converter import is_video_file
from bot.services.unzipper import is_archive_file


def test_video_format_detection():
    # Valid video formats
    assert is_video_file("movie.mkv") is True
    assert is_video_file("clip.avi") is True
    assert is_video_file("video.mp4") is True
    assert is_video_file("stream.ts") is True
    assert is_video_file("web_recording.webm") is True
    assert is_video_file("camera.mov") is True
    assert is_video_file("old_phone.3gp") is True

    # Non-video formats
    assert is_video_file("archive.zip") is False
    assert is_video_file("document.pdf") is False
    assert is_video_file("song.mp3") is False
    assert is_video_file("photo.jpg") is False


def test_archive_format_detection():
    # Valid archive formats
    assert is_archive_file("package.zip") is True
    assert is_archive_file("backup.rar") is True
    assert is_archive_file("data.7z") is True
    assert is_archive_file("archive.tar") is True
    assert is_archive_file("compressed.tar.gz") is True
    assert is_archive_file("source.tgz") is True
    assert is_archive_file("dist.tar.bz2") is True

    # Non-archive formats
    assert is_archive_file("video.mp4") is False
    assert is_archive_file("document.docx") is False
    assert is_archive_file("installer.exe") is False
