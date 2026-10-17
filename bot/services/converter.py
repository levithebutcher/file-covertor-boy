"""
High-performance FFmpeg video conversion service.
Converts any popular video format to MP4 with live progress, stream copying, and cancellation.
"""

from __future__ import annotations

import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from bot.utils.progress import ProgressReporter
from bot.utils.media_info import get_video_metadata, extract_thumbnail
from bot.services.queue import queue_manager

logger = logging.getLogger(__name__)

# Supported popular video extensions
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
    ".ts", ".m2ts", ".3gp", ".mpg", ".mpeg", ".m4v",
    ".ogv", ".vob", ".rmvb", ".divx", ".asf", ".mp4",
}


def is_video_file(filename: str, mime_type: Optional[str] = None) -> bool:
    """Check if file has a recognizable video extension or mime type."""
    ext = Path(filename).suffix.lower()
    if ext in SUPPORTED_VIDEO_EXTENSIONS:
        return True
    if mime_type and mime_type.startswith("video/"):
        return True
    return False


def parse_time_to_seconds(time_str: str) -> float:
    """Convert HH:MM:SS.micro to total seconds."""
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600.0 + m * 60.0 + s
    except Exception:
        pass
    return 0.0


async def convert_to_mp4(
    input_file: Path,
    output_file: Path,
    task_id: str,
    reporter: ProgressReporter,
) -> Tuple[bool, Dict[str, Any], Optional[Path]]:
    """
    Convert video file to optimized streaming MP4 (H.264/AAC).
    Returns (success, metadata, thumbnail_path).
    """
    metadata = await get_video_metadata(input_file)
    duration = metadata.get("duration", 0)
    input_size = input_file.stat().st_size
    vcodec = metadata.get("vcodec", "")
    acodec = metadata.get("acodec", "")
    height = metadata.get("height", 720)
    has_audio = acodec not in ("unknown", "", "none", None)

    # Prepare thumbnail in the same directory
    thumb_path = input_file.parent / f"{task_id}_thumb.jpg"
    await extract_thumbnail(input_file, thumb_path, seek_seconds=min(2.0, max(0.5, duration / 10.0)))

    # Determine command:
    # 1. Full Stream Copy if both H.264 video and AAC/MP3 audio
    # 2. Video Stream Copy if H.264 video with other audio format or silent synthesis
    # 3. High-efficiency Transcode optimized for Render free tier (0.1 vCPU, 512MB RAM)
    if vcodec == "h264" and has_audio and acodec in ("aac", "mp3"):
        logger.info("Streams are already H.264/AAC. Using instant direct stream copy for %s", input_file.name)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_file.resolve()),
            "-c", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(output_file.resolve()),
        ]
    elif vcodec == "h264" and has_audio:
        logger.info("Video is already H.264. Copying video, re-encoding audio for %s", input_file.name)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_file.resolve()),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(output_file.resolve()),
        ]
    elif vcodec == "h264" and not has_audio:
        logger.info("Video is H.264 without audio. Synthesizing silent audio so Telegram renders full video player for %s", input_file.name)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_file.resolve()),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "64k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(output_file.resolve()),
        ]
    else:
        # Non-H.264 containers (e.g. WebM VP8/VP9/AV1, AVI, MKV, WMV)
        logger.info(
            "Transcoding %s (vcodec: %s, acodec: %s, height: %s, has_audio: %s) to H.264 MP4",
            input_file.name, vcodec, acodec, height, has_audio
        )
        if has_audio:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_file.resolve()),
                "-map", "0:v:0", "-map", "0:a:0?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "28",
                "-threads", "2",
            ]
            if height > 720:
                cmd.extend(["-vf", "scale=-2:720:flags=fast_bilinear"])
            cmd.extend(["-pix_fmt", "yuv420p"])

            if acodec in ("aac", "mp3"):
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2"])

            cmd.extend([
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                str(output_file.resolve()),
            ])
        else:
            # Video with NO audio track (e.g. silent WebM): inject silent stereo AAC so Telegram renders video controls
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_file.resolve()),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "28",
                "-threads", "2",
            ]
            if height > 720:
                cmd.extend(["-vf", "scale=-2:720:flags=fast_bilinear"])
            cmd.extend([
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "64k",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                str(output_file.resolve()),
            ])

    reporter.set_phase("Converting", total_bytes=input_size)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await queue_manager.set_process(task_id, proc)

        # Read ffmpeg progress from pipe:1
        while True:
            if reporter.is_cancelled:
                proc.terminate()
                break

            line = await proc.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str or "=" not in line_str:
                continue

            key, value = line_str.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key == "out_time":
                current_secs = parse_time_to_seconds(value)
                if duration > 0:
                    percent = min(99.0, (current_secs / duration) * 100.0)
                    simulated_bytes = int((percent / 100.0) * input_size)
                    await reporter.update(simulated_bytes, total_bytes=input_size)

            elif key == "progress" and value == "end":
                break

        await proc.wait()

        if reporter.is_cancelled:
            logger.info("Task %s was cancelled during conversion.", task_id)
            return False, metadata, None

        if proc.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
            logger.info("Conversion finished successfully for %s", output_file.name)
            # Re-probe final output metadata to ensure valid duration and dimensions
            final_meta = await get_video_metadata(output_file)
            return True, final_meta, (thumb_path if thumb_path.exists() else None)
        else:
            _, stderr = await proc.communicate()
            logger.error("FFmpeg exited with code %s: %s", proc.returncode, stderr.decode("utf-8", errors="replace")[:400])
            return False, metadata, None

    except asyncio.CancelledError:
        logger.warning("Conversion task %s cancelled by asyncio event.", task_id)
        return False, metadata, None
    except Exception as e:
        logger.error("Conversion failed for task %s: %s", task_id, e)
        return False, metadata, None
