"""
Media metadata extraction using ffprobe and thumbnail generation using ffmpeg.
"""

from __future__ import annotations

import json
import asyncio
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


async def get_video_metadata(file_path: Path | str) -> Dict[str, Any]:
    """
    Probe video container and streams using ffprobe.
    Returns dictionary with: duration, width, height, vcodec, acodec.
    """
    p = str(Path(file_path).resolve())
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        p,
    ]

    metadata = {
        "duration": 0,
        "width": 1280,
        "height": 720,
        "vcodec": "unknown",
        "acodec": "unknown",
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or not stdout:
            return metadata

        info = json.loads(stdout.decode("utf-8", errors="replace"))

        # Extract format duration
        if "format" in info and "duration" in info["format"]:
            try:
                metadata["duration"] = max(1, int(round(float(info["format"]["duration"]))))
            except (ValueError, TypeError):
                pass

        # Inspect streams
        for stream in info.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and metadata["vcodec"] == "unknown":
                metadata["vcodec"] = stream.get("codec_name", "unknown")
                metadata["width"] = int(stream.get("width", 1280))
                metadata["height"] = int(stream.get("height", 720))
                if not metadata["duration"] and "duration" in stream:
                    try:
                        metadata["duration"] = max(1, int(round(float(stream["duration"]))))
                    except (ValueError, TypeError):
                        pass
            elif codec_type == "audio" and metadata["acodec"] == "unknown":
                metadata["acodec"] = stream.get("codec_name", "unknown")

    except FileNotFoundError:
        logger.warning("ffprobe executable not found on system. Using fallback metadata.")
    except Exception as e:
        logger.error("Failed to inspect video metadata for %s: %s", file_path, e)

    return metadata


async def extract_thumbnail(
    video_path: Path | str,
    output_thumb_path: Path | str,
    seek_seconds: float = 2.0,
) -> bool:
    """
    Extract a single frame thumbnail at seek_seconds using ffmpeg.
    """
    in_path = str(Path(video_path).resolve())
    out_path = str(Path(output_thumb_path).resolve())

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(seek_seconds),
        "-i", in_path,
        "-vframes", "1",
        "-vf", "scale=320:-1",
        "-q:v", "3",
        out_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0 and Path(out_path).exists()
    except FileNotFoundError:
        logger.warning("ffmpeg executable not found for thumbnail generation.")
        return False
    except Exception as e:
        logger.error("Error generating thumbnail: %s", e)
        return False
