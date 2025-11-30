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


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def _write_srt_for_preview(
    subtitles: List[Dict[str, Any]],
    clip_start: float,
    path: Path,
) -> Path:
    """Write SRT file for clip preview, adjusting timestamps relative to clip start."""
    lines = []
    for idx, seg in enumerate(subtitles, 1):
        start = max(seg["start_time_sec"] - clip_start, 0)
        end = max(seg["end_time_sec"] - clip_start, start + 0.1)
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
        lines.append(seg["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _escape_ffmpeg_path(path: str) -> str:
    """Escape path for ffmpeg filter on Windows and Unix."""
    # Convert backslashes to forward slashes
    escaped = path.replace("\\", "/")
    # Escape colons (but not drive letter on Windows like C:)
    # For Windows paths like D:/path, we need to escape the colon after drive letter
    if len(escaped) >= 2 and escaped[1] == ":":
        # Windows path with drive letter - escape the colon
        escaped = escaped[0] + "\\:" + escaped[2:]
    # Escape other special characters
    escaped = escaped.replace("'", "\\'")
    return escaped


def _get_default_viral_style(aspect_ratio: str = "9:16") -> Dict[str, Any]:
    """
    Get default viral-style subtitle settings optimized for social media.
    Font size and margins are calculated based on video resolution.
    
    ASS Alignment (numpad layout):
        7=TopLeft    8=TopCenter    9=TopRight
        4=MidLeft    5=MidCenter    6=MidRight
        1=BotLeft    2=BotCenter    3=BotRight
    
    Resolutions:
        9:16 = 1080x1920 (Portrait/TikTok/Reels)
        1:1  = 1080x1080 (Square/Instagram)
        16:9 = 1920x1080 (Landscape/YouTube)
    """
    # Style settings per aspect ratio
    # Font size ~4% of video height for readability
    # MarginV ~15% from bottom for safe area (avoid UI elements on mobile)
    # MarginL/R ~5% for padding from edges
    styles = {
        "9:16": {
            "fontSize": 76,      # 1920 * 0.04 = ~76
            "marginV": 290,      # 1920 * 0.15 = ~290 (above mobile nav/buttons)
            "marginL": 54,       # 1080 * 0.05 = ~54
            "marginR": 54,
            "outlineWidth": 4,
        },
        "1:1": {
            "fontSize": 44,      # 1080 * 0.04 = ~44
            "marginV": 160,      # 1080 * 0.15 = ~160
            "marginL": 54,       # 1080 * 0.05 = ~54
            "marginR": 54,
            "outlineWidth": 3,
        },
        "16:9": {
            "fontSize": 44,      # 1080 * 0.04 = ~44
            "marginV": 80,       # 1080 * 0.075 = ~80 (less margin needed for landscape)
            "marginL": 96,       # 1920 * 0.05 = ~96
            "marginR": 96,
            "outlineWidth": 3,
        },
    }
    
    s = styles.get(aspect_ratio, styles["9:16"])
    
    return {
        "fontFamily": "Arial Black",
        "fontSize": s["fontSize"],
        "fontColor": "#FFFFFF",
        "bold": True,
        "italic": False,
        "outlineWidth": s["outlineWidth"],
        "outlineColor": "#000000",
        "shadowOffset": 0,          # No shadow, clean look
        "alignment": 2,             # Bottom center
        "marginV": s["marginV"],    # Distance from bottom
        "marginL": s["marginL"],    # Left padding
        "marginR": s["marginR"],    # Right padding
        "spacing": 0,
        "borderStyle": 1,           # Outline + drop shadow
    }


def _build_subtitle_filter(
    srt_path: str,
    style_json: Optional[Dict[str, Any]] = None,
    aspect_ratio: str = "9:16",
    video_width: int = 1080,
    video_height: int = 1920,
) -> str:
    """
    Build ffmpeg subtitles filter with viral-optimized styling.
    If no style provided, uses default viral style based on aspect ratio.
    
    IMPORTANT: We must specify original_size to match the output video resolution,
    otherwise ffmpeg uses default ASS PlayRes (384x288) which makes fonts tiny.
    """
    srt_escaped = _escape_ffmpeg_path(srt_path)
    
    # Use default viral style if none provided, merge with custom style
    default_style = _get_default_viral_style(aspect_ratio)
    if style_json:
        # Merge custom style with defaults (custom takes precedence)
        merged_style = {**default_style, **style_json}
    else:
        merged_style = default_style
    
    # Extract style properties
    font_name = merged_style.get("fontFamily", "Arial Black")
    font_size = merged_style.get("fontSize", 72)
    font_color = merged_style.get("fontColor", "#FFFFFF").lstrip("#")
    bold = 1 if merged_style.get("bold", True) else 0
    italic = 1 if merged_style.get("italic", False) else 0
    outline_width = merged_style.get("outlineWidth", 4)
    outline_color = merged_style.get("outlineColor", "#000000").lstrip("#")
    shadow_offset = merged_style.get("shadowOffset", 2)
    alignment = merged_style.get("alignment", 2)
    margin_v = merged_style.get("marginV", 120)
    margin_l = merged_style.get("marginL", 40)
    margin_r = merged_style.get("marginR", 40)
    spacing = merged_style.get("spacing", 0)
    border_style = merged_style.get("borderStyle", 1)
    
    # Convert hex colors to ASS format (&HBBGGRR)
    def hex_to_ass(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}&"
        return "&H00FFFFFF&"
    
    primary_color = hex_to_ass(font_color)
    outline_color_ass = hex_to_ass(outline_color)
    back_color = "&H80000000&"  # Semi-transparent black for shadow
    
    # Build comprehensive ASS force_style
    force_style = (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour={primary_color},"
        f"OutlineColour={outline_color_ass},"
        f"BackColour={back_color},"
        f"Bold={bold},"
        f"Italic={italic},"
        f"Outline={outline_width},"
        f"Shadow={shadow_offset},"
        f"Alignment={alignment},"
        f"MarginV={margin_v},"
        f"MarginL={margin_l},"
        f"MarginR={margin_r},"
        f"Spacing={spacing},"
        f"BorderStyle={border_style}"
    )
    
    # CRITICAL: original_size tells ffmpeg the reference resolution for font scaling
    # Without this, ffmpeg uses 384x288 (ASS default) making fonts appear tiny
    return f"subtitles='{srt_escaped}':original_size={video_width}x{video_height}:force_style='{force_style}'"


def render_clip_preview(
    source_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    aspect_ratio: str = "9:16",
    subtitles: Optional[List[Dict[str, Any]]] = None,
    subtitle_style: Optional[Dict[str, Any]] = None,
    subtitle_enabled: bool = True,
) -> bool:
    """
    Render clip preview with optional subtitles and styling.
    
    Uses letterbox/pillarbox approach to fit video into target aspect ratio
    without cropping - adds black bars where needed to preserve all content.
    
    Args:
        source_path: Path to source video
        output_path: Path for output video
        start_sec: Start time in seconds
        duration_sec: Duration in seconds
        aspect_ratio: Target aspect ratio ("9:16", "1:1", "16:9")
        subtitles: List of subtitle dicts with start_time_sec, end_time_sec, text
        subtitle_style: Style dict with fontFamily, fontSize, fontColor, etc.
        subtitle_enabled: Whether to render subtitles
    """
    # Build scale+pad filter based on target aspect ratio
    # Define output dimensions for each aspect ratio
    if aspect_ratio == "9:16":
        video_width, video_height = 1080, 1920
    elif aspect_ratio == "1:1":
        video_width, video_height = 1080, 1080
    else:  # 16:9
        video_width, video_height = 1920, 1080
    
    scale_filter = f"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2:black"

    # Prepare subtitle filter if subtitles provided and enabled
    srt_path = None
    video_filter = scale_filter
    
    if subtitle_enabled and subtitles and len(subtitles) > 0:
        output_dir = Path(output_path).parent
        srt_path = output_dir / "preview_subs.srt"
        _write_srt_for_preview(subtitles, start_sec, srt_path)
        subtitle_filter = _build_subtitle_filter(
            str(srt_path), 
            subtitle_style, 
            aspect_ratio,
            video_width,
            video_height,
        )
        video_filter = f"{scale_filter},{subtitle_filter}"

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-ss", str(start_sec),
        "-i", source_path,
        "-t", str(duration_sec),
        "-vf", video_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    code, _, err = run_cmd(cmd)
    
    # If subtitle rendering failed, retry without subtitles
    if code != 0 and srt_path is not None:
        logger.warning(
            "ffmpeg.subtitle_render_failed_retrying_without",
            error=err,
            output_path=output_path
        )
        # Cleanup failed srt
        if srt_path.exists():
            try:
                srt_path.unlink()
            except Exception:
                pass
        # Retry without subtitles
        cmd_no_subs = [
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
        code, _, err = run_cmd(cmd_no_subs)
    
    # Cleanup temp srt file
    if srt_path and srt_path.exists():
        try:
            srt_path.unlink()
        except Exception:
            pass
    
    if code != 0:
        logger.error("ffmpeg.clip_preview_failed", error=err, output_path=output_path)
        return False
    logger.info("ffmpeg.clip_preview_done", output_path=output_path)
    return True
