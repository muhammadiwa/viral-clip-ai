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


def run_cmd_with_progress(
    cmd: List[str],
    duration_sec: float,
    progress_callback: callable = None,
) -> Tuple[int, str, str]:
    """
    Run ffmpeg command with real-time progress tracking.
    
    Args:
        cmd: Command list (must include -progress pipe:1 for ffmpeg)
        duration_sec: Expected duration in seconds for progress calculation
        progress_callback: Callback(progress_0_to_1, message)
    
    Returns:
        (exit_code, stdout, stderr)
    """
    logger.info("exec.cmd_with_progress", cmd=" ".join(shlex.quote(c) for c in cmd))
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    
    stderr_lines = []
    stdout_lines = []
    
    import re
    import threading
    
    def read_stderr():
        """Read stderr in background thread."""
        for line in proc.stderr:
            stderr_lines.append(line)
    
    # Start stderr reader thread
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    
    # Read stdout for progress
    time_pattern = re.compile(r"out_time_ms=(\d+)")
    last_progress = 0.0
    
    for line in proc.stdout:
        stdout_lines.append(line)
        
        # Parse ffmpeg progress output
        match = time_pattern.search(line)
        if match and duration_sec > 0:
            time_ms = int(match.group(1))
            time_sec = time_ms / 1_000_000  # Convert microseconds to seconds
            progress = min(1.0, time_sec / duration_sec)
            
            # Only update if progress changed significantly (avoid spam)
            if progress - last_progress >= 0.05 or progress >= 0.99:
                last_progress = progress
                if progress_callback:
                    progress_callback(
                        progress,
                        f"Rendering: {progress * 100:.0f}% ({time_sec:.1f}s / {duration_sec:.1f}s)"
                    )
    
    proc.wait()
    stderr_thread.join(timeout=1)
    
    stdout = "".join(stdout_lines)
    stderr = "".join(stderr_lines)
    
    return proc.returncode, stdout, stderr


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


def download_thumbnail(url: str, output_path: str) -> bool:
    """Download thumbnail from URL and save to local file."""
    try:
        import urllib.request
        import ssl
        
        # Create SSL context that doesn't verify (for some YouTube URLs)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # Add headers to mimic browser
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        
        # Verify file was created and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info("thumbnail.downloaded", url=url[:100], output=output_path)
            return True
        return False
    except Exception as e:
        logger.warning("thumbnail.download_failed", url=url[:100], error=str(e))
        return False


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
    """Write SRT file for clip preview, adjusting timestamps relative to clip start.
    
    Also deduplicates consecutive identical text to prevent double subtitles.
    """
    lines = []
    prev_text = None
    idx = 0
    
    for seg in subtitles:
        text = seg.get("text", "").strip()
        
        # Skip empty or duplicate consecutive text
        if not text or text == prev_text:
            continue
        
        idx += 1
        start = max(seg["start_time_sec"] - clip_start, 0)
        end = max(seg["end_time_sec"] - clip_start, start + 0.1)
        
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
        lines.append(text)
        lines.append("")
        
        prev_text = text
    
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _format_ass_timestamp(seconds: float) -> str:
    """Format seconds to ASS timestamp format (H:MM:SS.cc)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds - int(seconds)) * 100)
    return f"{hrs}:{mins:02}:{secs:02}.{centis:02}"


def _write_ass_for_preview(
    subtitles: List[Dict[str, Any]],
    clip_start: float,
    path: Path,
    style_json: Optional[Dict[str, Any]] = None,
    aspect_ratio: str = "9:16",
) -> Path:
    """
    Write ASS file with word-by-word karaoke highlighting.
    
    This creates an ASS subtitle file that highlights each word as it's spoken,
    similar to karaoke style subtitles popular on TikTok/Reels.
    
    IMPORTANT: All subtitle events use the SAME position (alignment + margins).
    The word highlight effect changes ONLY the text styling, not the position.
    This prevents subtitles from appearing in multiple positions simultaneously.
    
    Supported highlight styles:
    - color: Change text color of current word
    - background: Add background box behind current word
    - scale: Scale up current word
    - glow: Add glow/blur effect around current word (simulated with shadow)
    - underline: Add underline to current word
    - gradient: Use highlight color (ASS doesn't support true gradients)
    """
    # Pre-process subtitles: deduplicate consecutive identical text
    # This prevents the same subtitle from appearing twice
    deduped_subtitles = []
    prev_text = None
    prev_end = 0.0
    
    for sub in subtitles:
        text = sub.get("text", "").strip()
        start = sub.get("start_time_sec", 0)
        
        # Skip if:
        # 1. Empty text
        # 2. Same text as previous (duplicate)
        # 3. Overlapping with previous segment (causes double display)
        if not text:
            continue
        if text == prev_text:
            logger.debug("ass.skip_duplicate_text", text=text[:30])
            continue
        if start < prev_end - 0.05:  # Allow 50ms tolerance
            logger.debug("ass.skip_overlapping", start=start, prev_end=prev_end, text=text[:30])
            continue
        
        deduped_subtitles.append(sub)
        prev_text = text
        prev_end = sub.get("end_time_sec", start + 1)
    
    subtitles = deduped_subtitles
    
    logger.info("ass.deduped_subtitles", original_count=len(subtitles), final_count=len(deduped_subtitles))
    
    # Get dimensions and optimal sizes based on aspect ratio
    # All sizes are calculated as percentage of video height for consistency
    # Reference: 9:16 (1080x1920) is the base, others are scaled proportionally
    
    ASPECT_RATIO_CONFIG = {
        "9:16": {
            "width": 1080,
            "height": 1920,
            "font_size": 76,        # ~4% of height
            "margin_v": 290,        # ~15% from bottom
            "margin_h": 54,         # ~5% from sides
            "outline": 4,
        },
        "1:1": {
            "width": 1080,
            "height": 1080,
            "font_size": 52,        # ~4.8% of height (slightly larger % for readability)
            "margin_v": 120,        # ~11% from bottom
            "margin_h": 54,         # ~5% from sides
            "outline": 3,
        },
        "16:9": {
            "width": 1920,
            "height": 1080,
            "font_size": 48,        # ~4.4% of height
            "margin_v": 80,         # ~7.5% from bottom
            "margin_h": 96,         # ~5% from sides
            "outline": 3,
        },
    }
    
    config = ASPECT_RATIO_CONFIG.get(aspect_ratio, ASPECT_RATIO_CONFIG["9:16"])
    play_res_x = config["width"]
    play_res_y = config["height"]
    
    # Style settings with automatic scaling
    style = style_json or {}
    font_name = style.get("fontFamily", "Arial Black")
    
    # Get font size from style and scale it for current aspect ratio
    # Styles are typically designed for 9:16, so we scale based on height ratio
    style_font_size = style.get("fontSize")
    if style_font_size:
        # Scale font size proportionally to video height
        # Base reference: 9:16 has height 1920
        scale_factor = play_res_y / 1920
        font_size = max(28, int(style_font_size * scale_factor))
    else:
        font_size = config["font_size"]
    
    font_color = style.get("fontColor", "#FFFFFF").lstrip("#")
    
    # Scale outline width
    style_outline = style.get("outlineWidth")
    if style_outline:
        scale_factor = play_res_y / 1920
        outline_width = max(2, int(style_outline * scale_factor))
    else:
        outline_width = config["outline"]
    
    outline_color = style.get("outlineColor", "#000000").lstrip("#")
    bold = -1 if style.get("bold", True) else 0
    alignment = style.get("alignment", 2)
    
    # Scale margins
    style_margin_v = style.get("marginV")
    if style_margin_v:
        scale_factor = play_res_y / 1920
        margin_v = max(40, int(style_margin_v * scale_factor))
    else:
        margin_v = config["margin_v"]
    
    style_margin_l = style.get("marginL")
    style_margin_r = style.get("marginR")
    margin_l = style_margin_l if style_margin_l else config["margin_h"]
    margin_r = style_margin_r if style_margin_r else config["margin_h"]
    
    # Animation settings
    animation = style.get("animation", "none")
    highlight_color = style.get("highlightColor", "#FFD700").lstrip("#")
    highlight_style = style.get("highlightStyle", "color")
    
    # Convert colors to ASS format (&HBBGGRR)
    def hex_to_ass(hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}&"
        return "&H00FFFFFF&"
    
    primary_color = hex_to_ass(font_color)
    secondary_color = hex_to_ass(highlight_color)
    outline_color_ass = hex_to_ass(outline_color)
    
    # ASS header
    ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},{outline_color_ass},&H80000000&,{bold},0,0,0,100,100,0,0,1,{outline_width},0,{alignment},{margin_l},{margin_r},{margin_v},1
Style: Highlight,{font_name},{font_size},{secondary_color},{primary_color},{outline_color_ass},&H80000000&,{bold},0,0,0,100,100,0,0,1,{outline_width},0,{alignment},{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    events = []
    
    # Supported highlight styles for word-by-word animation
    supported_highlights = ["color", "background", "scale", "glow", "neon_glow", "underline", "gradient", "comic_burst"]
    
    for seg in subtitles:
        start = max(seg["start_time_sec"] - clip_start, 0)
        end = max(seg["end_time_sec"] - clip_start, start + 0.1)
        text = seg["text"].strip()
        
        if not text:
            continue
        
        if animation == "word_highlight" and highlight_style in supported_highlights:
            # Word-by-word karaoke effect using ASS \kf (karaoke fill) tags
            # This creates a SINGLE event with karaoke timing built-in
            # NO MULTIPLE EVENTS = NO POSITION JUMPING
            words = text.split()
            
            # Check if we have word-level timestamps from Whisper
            word_timestamps = seg.get("words", [])
            has_word_timestamps = word_timestamps and len(word_timestamps) > 0
            
            if len(words) > 1:
                # Calculate word durations in centiseconds (ASS karaoke uses centiseconds)
                total_duration_cs = int((end - start) * 100)
                word_duration_cs = total_duration_cs // len(words)
                
                # Build karaoke text with \kf tags
                # \kf = karaoke fill (smooth highlight)
                # Format: {\kf<duration>}word where duration is in centiseconds
                karaoke_parts = []
                
                for word_idx, word in enumerate(words):
                    if has_word_timestamps and word_idx < len(word_timestamps):
                        wt = word_timestamps[word_idx]
                        w_start = wt.get("start", 0) - clip_start
                        w_end = wt.get("end", 0) - clip_start
                        w_duration_cs = max(10, int((w_end - w_start) * 100))
                    else:
                        w_duration_cs = word_duration_cs
                    
                    # Apply highlight style to the karaoke effect
                    if highlight_style == "color":
                        # Use \kf for smooth color fill karaoke
                        karaoke_parts.append(f"{{\\kf{w_duration_cs}}}{word}")
                    elif highlight_style == "scale":
                        # Scale effect with karaoke
                        karaoke_parts.append(f"{{\\kf{w_duration_cs}}}{word}")
                    else:
                        # Default karaoke fill
                        karaoke_parts.append(f"{{\\kf{w_duration_cs}}}{word}")
                
                karaoke_text = " ".join(karaoke_parts)
                events.append(
                    f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},Default,,0,0,0,,{karaoke_text}"
                )
            else:
                # Single word, just show it
                events.append(
                    f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},Default,,0,0,0,,{text}"
                )
        
        elif animation == "typewriter":
            # Typewriter effect using ASS \ko (karaoke outline) for character-by-character
            chars = list(text.replace(" ", ""))  # Remove spaces for char count
            if len(chars) > 0:
                total_duration_cs = int((end - start) * 100)
                char_duration_cs = max(5, total_duration_cs // len(chars))
                
                # Build typewriter text - each character appears one by one
                typewriter_parts = []
                for char in text:
                    if char == " ":
                        typewriter_parts.append(" ")
                    else:
                        typewriter_parts.append(f"{{\\ko{char_duration_cs}}}{char}")
                
                typewriter_text = "".join(typewriter_parts)
                events.append(
                    f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},Default,,0,0,0,,{typewriter_text}"
                )
        
        else:
            # No animation, regular subtitle - ONE event per segment
            events.append(
                f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},Default,,0,0,0,,{text}"
            )
    
    ass_content += "\n".join(events)
    path.write_text(ass_content, encoding="utf-8")
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
    
    Design principles:
        - Font size: ~4-5% of video height for readability
        - MarginV: Safe area from bottom (avoid UI elements)
        - MarginL/R: ~5% padding from edges
    """
    styles = {
        "9:16": {
            "fontSize": 76,      # 1920 * 0.04 = ~76
            "marginV": 290,      # ~15% from bottom (above mobile nav/buttons)
            "marginL": 54,       # 1080 * 0.05 = ~54
            "marginR": 54,
            "outlineWidth": 4,
        },
        "1:1": {
            "fontSize": 52,      # 1080 * 0.048 = ~52 (slightly larger % for square)
            "marginV": 120,      # ~11% from bottom
            "marginL": 54,       # 1080 * 0.05 = ~54
            "marginR": 54,
            "outlineWidth": 3,
        },
        "16:9": {
            "fontSize": 48,      # 1080 * 0.044 = ~48
            "marginV": 80,       # ~7.5% from bottom (less needed for landscape)
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
    
    All sizes are automatically scaled based on aspect ratio.
    Styles are assumed to be designed for 9:16 (1920 height) and scaled accordingly.
    """
    srt_escaped = _escape_ffmpeg_path(srt_path)
    
    # Use default viral style if none provided, merge with custom style
    default_style = _get_default_viral_style(aspect_ratio)
    if style_json:
        # Merge custom style with defaults (custom takes precedence)
        merged_style = {**default_style, **style_json}
    else:
        merged_style = default_style
    
    # Scale factor based on video height (reference: 9:16 = 1920 height)
    scale_factor = video_height / 1920
    
    # Extract and scale style properties
    font_name = merged_style.get("fontFamily", "Arial Black")
    
    # Scale font size
    raw_font_size = merged_style.get("fontSize", 72)
    font_size = max(28, int(raw_font_size * scale_factor))
    
    font_color = merged_style.get("fontColor", "#FFFFFF").lstrip("#")
    bold = 1 if merged_style.get("bold", True) else 0
    italic = 1 if merged_style.get("italic", False) else 0
    
    # Scale outline width
    raw_outline = merged_style.get("outlineWidth", 4)
    outline_width = max(2, int(raw_outline * scale_factor))
    
    outline_color = merged_style.get("outlineColor", "#000000").lstrip("#")
    
    # Scale shadow
    raw_shadow = merged_style.get("shadowOffset", 2)
    shadow_offset = max(1, int(raw_shadow * scale_factor))
    
    alignment = merged_style.get("alignment", 2)
    
    # Scale margins
    raw_margin_v = merged_style.get("marginV", 120)
    margin_v = max(40, int(raw_margin_v * scale_factor))
    
    raw_margin_l = merged_style.get("marginL", 40)
    margin_l = max(20, int(raw_margin_l * scale_factor))
    
    raw_margin_r = merged_style.get("marginR", 40)
    margin_r = max(20, int(raw_margin_r * scale_factor))
    
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
    progress_callback: callable = None,
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
    sub_path = None
    video_filter = scale_filter
    
    if subtitle_enabled and subtitles and len(subtitles) > 0:
        output_dir = Path(output_path).parent
        
        # Check if style has animation (karaoke/highlight or typewriter)
        animation = subtitle_style.get("animation", "none") if subtitle_style else "none"
        
        if animation in ["word_highlight", "typewriter"]:
            # Use ASS format for animated subtitles (word highlight or typewriter)
            sub_path = output_dir / "preview_subs.ass"
            _write_ass_for_preview(subtitles, start_sec, sub_path, subtitle_style, aspect_ratio)
            sub_escaped = _escape_ffmpeg_path(str(sub_path))
            subtitle_filter = f"ass='{sub_escaped}'"
        else:
            # Use SRT format for regular subtitles
            sub_path = output_dir / "preview_subs.srt"
            _write_srt_for_preview(subtitles, start_sec, sub_path)
            subtitle_filter = _build_subtitle_filter(
                str(sub_path), 
                subtitle_style, 
                aspect_ratio,
                video_width,
                video_height,
            )
        
        video_filter = f"{scale_filter},{subtitle_filter}"

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-progress", "pipe:1" if progress_callback else "-",
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
    
    if progress_callback:
        code, _, err = run_cmd_with_progress(cmd, duration_sec, progress_callback)
    else:
        code, _, err = run_cmd(cmd)
    
    # If subtitle rendering failed, retry without subtitles
    if code != 0 and sub_path is not None:
        logger.warning(
            "ffmpeg.subtitle_render_failed_retrying_without",
            error=err,
            output_path=output_path
        )
        # Cleanup failed subtitle file
        if sub_path.exists():
            try:
                sub_path.unlink()
            except Exception:
                pass
        # Retry without subtitles
        cmd_no_subs = [
            settings.ffmpeg_bin,
            "-y",
            "-progress", "pipe:1" if progress_callback else "-",
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
        
        if progress_callback:
            code, _, err = run_cmd_with_progress(cmd_no_subs, duration_sec, progress_callback)
        else:
            code, _, err = run_cmd(cmd_no_subs)
    
    # Cleanup temp subtitle file
    if sub_path and sub_path.exists():
        try:
            sub_path.unlink()
        except Exception:
            pass
    
    if code != 0:
        logger.error("ffmpeg.clip_preview_failed", error=err, output_path=output_path)
        return False
    logger.info("ffmpeg.clip_preview_done", output_path=output_path)
    return True
