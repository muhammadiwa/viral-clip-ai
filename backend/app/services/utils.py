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
