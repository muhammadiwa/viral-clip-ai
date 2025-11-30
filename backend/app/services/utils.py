import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_openai_client() -> Optional["OpenAI"]:
    if not settings.openai_api_key or OpenAI is None:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    logger.info("exec.cmd", cmd=" ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out, err


def probe_duration(path: str) -> Optional[float]:
    cmd = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    code, out, _ = run_cmd(cmd)
    if code != 0:
        return None
    try:
        return float(out.strip())
    except Exception:
        return None


def probe_fps(path: str) -> Optional[float]:
    cmd = [
        settings.ffprobe_bin,
        "-v",
        "0",
        "-select_streams",
        "v:0",
        "-print_format",
        "flat",
        "-show_entries",
        "stream=r_frame_rate",
        path,
    ]
    code, out, _ = run_cmd(cmd)
    if code != 0:
        return None
    try:
        # parse e.g. "stream.0.r_frame_rate=\"30000/1001\""
        for line in out.splitlines():
            if "r_frame_rate" in line:
                rate = line.split("=")[1].strip().strip('"')
                num, denom = rate.split("/")
                return float(num) / float(denom)
    except Exception:
        return None
    return None


def extract_audio(source_path: str, output_path: str, start: float = 0.0, duration: Optional[float] = None) -> bool:
    cmd = [settings.ffmpeg_bin, "-y", "-i", source_path, "-vn", "-ac", "1", "-ar", "16000"]
    if start:
        cmd.extend(["-ss", str(start)])
    if duration:
        cmd.extend(["-t", str(duration)])
    cmd.append(output_path)
    code, _, err = run_cmd(cmd)
    if code != 0:
        logger.error("ffmpeg.extract_audio_failed", error=err)
        return False
    return True


def render_thumbnail(source_path: str, output_path: str, timestamp: float) -> bool:
    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-ss",
        str(timestamp),
        "-i",
        source_path,
        "-vframes",
        "1",
        "-q:v",
        "2",
        output_path,
    ]
    code, _, err = run_cmd(cmd)
    if code != 0:
        logger.error("ffmpeg.thumbnail_failed", error=err)
        return False
    return True


def render_clip_preview(
    source_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    aspect_ratio: str = "9:16",
) -> bool:
    """
    Render a simple clip preview (cut from source video) without subtitles or brand kit.
    Used for auto-generating clip previews during clip generation.
    """
    # Build scale filter based on aspect ratio
    if aspect_ratio == "9:16":
        scale_filter = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    elif aspect_ratio == "1:1":
        scale_filter = "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2"
    else:  # 16:9
        scale_filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-ss", str(start_sec),
        "-i", source_path,
        "-t", str(duration_sec),
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    code, _, err = run_cmd(cmd)
    if code != 0:
        logger.error("ffmpeg.clip_preview_failed", error=err, output_path=output_path)
        return False
    logger.info("ffmpeg.clip_preview_done", output_path=output_path)
    return True
