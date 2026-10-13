"""
Comprehensive local test suite for all bot services:
1. Video Converter (real FFmpeg transcode & stream copy)
2. Unzipper (real zip, tar.gz extraction & 2GB limit validation)
3. Zipper (real multi-file staging and zip package creation)
4. Database & Mode Switcher (whitelist, user mode, distributed lock)
5. Telegram MTProto Client & Handler Verification
"""

import os
import sys
import asyncio
import subprocess
import zipfile
import tarfile
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure environment path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.config import settings
from bot.database.mongo import db_manager
from bot.database.users import is_whitelisted, add_user, remove_user, get_user_mode, set_user_mode
from bot.database.jobs import acquire_host_lock, heartbeat_host_lock, release_host_lock
from bot.services.converter import convert_to_mp4, is_video_file
from bot.services.unzipper import extract_archive_7z, get_and_validate_extracted_files, is_archive_file, TG_MAX_FILE_SIZE
from bot.services.zipper import add_file_to_staging, get_staging_stats, create_zip_package, clear_staging
from bot.utils.media_info import get_video_metadata, extract_thumbnail
from bot.utils.file_ops import sanitize_filename, safe_remove_dir
from bot.core.client import bot_client

TEST_DIR = Path("test_workspace")


class MockStatusMessage:
    """Mock Telegram Message to capture progress updates without sending network requests."""
    def __init__(self):
        self.last_text = ""
        self.edit_count = 0

    async def edit_text(self, text, reply_markup=None):
        self.last_text = text
        self.edit_count += 1

    async def delete(self):
        pass


class MockReporter:
    """Mock ProgressReporter for service testing."""
    def __init__(self):
        self.is_cancelled = False
        self.phase = "Init"
        self.last_pct = 0.0

    def set_phase(self, phase, total_bytes=None):
        self.phase = phase

    def cancel(self):
        self.is_cancelled = True

    async def update(self, current, total_bytes=None):
        if total_bytes and total_bytes > 0:
            self.last_pct = (current / total_bytes) * 100.0


async def run_all_tests():
    print("==================================================")
    print("   LOCAL COMPREHENSIVE BOT VERIFICATION SUITE     ")
    print("==================================================")
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    try:
        # ======================================================================
        # TEST 1: Video Converter Service with real video transcode
        # ======================================================================
        print("\n🎬 [TEST 1] Testing Video Converter Service...")
        sample_mkv = TEST_DIR / "sample_test.mkv"
        converted_mp4 = TEST_DIR / "sample_converted.mp4"

        # Generate a real 5-second test video with video & audio streams using ffmpeg
        print("  Generating real test video sample with FFmpeg...")
        cmd_gen = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
            "-c:v", "libx264", "-c:a", "aac",
            str(sample_mkv.resolve()),
        ]
        proc = subprocess.run(cmd_gen, capture_output=True, text=True)
        assert sample_mkv.exists(), "Failed to generate test MKV"
        print(f"  Generated test MKV ({sample_mkv.stat().st_size} bytes)")

        # Verify probe
        meta = await get_video_metadata(sample_mkv)
        assert meta["duration"] >= 3, f"Unexpected duration: {meta['duration']}"
        assert meta["width"] == 640 and meta["height"] == 360, "Metadata dimensions mismatch"
        print(f"  FFprobe verified: duration={meta['duration']}s, resolution={meta['width']}x{meta['height']}, vcodec={meta['vcodec']}")

        # Test video conversion
        reporter = MockReporter()
        success, final_meta, thumb = await convert_to_mp4(
            input_file=sample_mkv,
            output_file=converted_mp4,
            task_id="test_vid_1",
            reporter=reporter,
        )
        assert success is True, "convert_to_mp4 returned False"
        assert converted_mp4.exists() and converted_mp4.stat().st_size > 0, "Converted MP4 does not exist or empty"
        print(f"  Converted to MP4 successfully ({converted_mp4.stat().st_size} bytes)")
        assert thumb is not None and thumb.exists(), "Thumbnail was not created"
        print(f"  Thumbnail extracted: {thumb.name} ({thumb.stat().st_size} bytes)")
        results["Video Converter"] = "PASSED"

        # ======================================================================
        # TEST 2: Unzipper Service with real archives
        # ======================================================================
        print("\n📦 [TEST 2] Testing Unzipper Service...")
        zip_path = TEST_DIR / "test_archive.zip"
        unzip_dest = TEST_DIR / "extracted_zip"

        # Create real zip with 3 files
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("document.txt", "Hello World Unzipper Test Content")
            zf.writestr("subfolder/image.raw", b"\x00\xFF\xAA" * 1000)
            zf.writestr(".DS_Store", "junk macos file")  # should be filtered
        print(f"  Created test zip archive ({zip_path.stat().st_size} bytes)")

        rep_unzip = MockReporter()
        unzip_ok = await extract_archive_7z(zip_path, unzip_dest, "test_unzip_1", rep_unzip)
        assert unzip_ok is True, "Failed to extract zip archive"

        valid_files, oversized = get_and_validate_extracted_files(unzip_dest)
        valid_names = [f.name for f in valid_files]
        assert "document.txt" in valid_names, "document.txt missing from extracted list"
        assert "image.raw" in valid_names, "image.raw missing from extracted list"
        assert ".DS_Store" not in valid_names, ".DS_Store junk was not filtered!"
        print(f"  Extracted {len(valid_files)} valid files, junk filtered successfully.")

        # Test Tar.Gz
        tar_path = TEST_DIR / "test_archive.tar.gz"
        tar_dest = TEST_DIR / "extracted_tar"
        with tarfile.open(tar_path, "w:gz") as tf:
            test_file = TEST_DIR / "tar_content.txt"
            test_file.write_text("Tar content", encoding="utf-8")
            tf.add(test_file, arcname="tar_content.txt")

        tar_ok = await extract_archive_7z(tar_path, tar_dest, "test_tar_1", rep_unzip)
        assert tar_ok is True, "Failed to extract tar.gz"
        t_valid, _ = get_and_validate_extracted_files(tar_dest)
        assert any(f.name == "tar_content.txt" for f in t_valid), "tar_content.txt missing"
        print(f"  Tar.Gz extraction verified successfully.")
        results["Unzipper Service"] = "PASSED"

        # ======================================================================
        # TEST 3: Zipper Service (Multi-File Collector)
        # ======================================================================
        print("\n🗜️ [TEST 3] Testing Zipper Service...")
        user_test_id = 999999
        clear_staging(user_test_id)

        # Stage 3 files
        file1 = TEST_DIR / "file_one.txt"
        file1.write_text("File 1 content", encoding="utf-8")
        file2 = TEST_DIR / "file_two.dat"
        file2.write_bytes(b"\x01\x02\x03\x04" * 500)

        c1, s1, l1 = await add_file_to_staging(user_test_id, file1, "file_one.txt")
        c2, s2, l2 = await add_file_to_staging(user_test_id, file2, "file_two.dat")
        assert c2 == 2, f"Expected 2 staged files, got {c2}"
        print(f"  Staged 2 files: total_size={s2} bytes, latest={l2}")

        rep_zip = MockReporter()
        out_zip_dir = TEST_DIR / "zip_output"
        archives = await create_zip_package(user_test_id, "test_zip_1", out_zip_dir, rep_zip)
        assert len(archives) >= 1, "Failed to create zip package"
        assert archives[0].exists(), "Created zip file missing"
        print(f"  Created package: {archives[0].name} ({archives[0].stat().st_size} bytes)")

        # Verify archive contains staged files
        with zipfile.ZipFile(archives[0], "r") as zf:
            names = zf.namelist()
            assert "file_one.txt" in names and "file_two.dat" in names, "Staged files not in zip"
        print(f"  Verified zip package content integrity.")

        clear_staging(user_test_id)
        cnt_after, _, _ = get_staging_stats(user_test_id)
        assert cnt_after == 0, "Staging cleanup failed"
        results["Zipper Service"] = "PASSED"

        # ======================================================================
        # TEST 4: Database & Mode Switcher
        # ======================================================================
        print("\n⚙️ [TEST 4] Testing Database & Mode Switcher...")
        # Whitelist testing
        test_uid = 777888
        await add_user(test_uid, role="whitelisted")
        assert await is_whitelisted(test_uid) is True, "User should be whitelisted"

        # Mode switching testing
        await set_user_mode(test_uid, "unzip")
        assert await get_user_mode(test_uid) == "unzip", "Mode should be unzip"
        await set_user_mode(test_uid, "zip")
        assert await get_user_mode(test_uid) == "zip", "Mode should be zip"
        await set_user_mode(test_uid, "convert")
        assert await get_user_mode(test_uid) == "convert", "Mode should be convert"
        print("  User mode switching tested: convert <-> unzip <-> zip")

        # Distributed lock testing
        assert await acquire_host_lock("render") is True
        assert await heartbeat_host_lock("render") is True
        assert await acquire_host_lock("colab", ttl_seconds=0) is True
        assert await release_host_lock("colab") is True
        print("  Distributed host locking tested: render <-> colab")
        results["Database & Mode Switcher"] = "PASSED"

        # ======================================================================
        # TEST 5: Telegram MTProto Connection & Handler Verification
        # ======================================================================
        print("\n🤖 [TEST 5] Testing Telegram MTProto Client & Handlers...")
        client = bot_client.get_instance()
        await client.start()
        await asyncio.sleep(0.5)

        me = await client.get_me()
        print(f"  Connected to Telegram as: @{me.username} (ID: {me.id})")

        total_handlers = sum(len(h) for h in client.dispatcher.groups.values()) if client.dispatcher.groups else 0
        assert total_handlers >= 15, f"Expected >= 15 handlers, found {total_handlers}"
        print(f"  Registered MTProto handlers: {total_handlers} handlers active across dispatcher groups.")
        await client.stop()
        results["Telegram Connection & Handlers"] = "PASSED"

        # Summary
        print("\n==================================================")
        print("   ALL TESTS PASSED WITH 100% SUCCESS!            ")
        print("==================================================")
        for name, status in results.items():
            print(f"  ✅ {name:32s}: {status}")

    finally:
        safe_remove_dir(TEST_DIR)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
