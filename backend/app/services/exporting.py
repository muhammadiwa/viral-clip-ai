from pathlib import Path
from typing import List, Optional

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ExportJob, SubtitleSegment
from app.services import dubbing, utils

logger = structlog.get_logger()
settings = get_settings()


def _format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"


def _write_srt(subtitles: List[SubtitleSegment], clip_start: float, path: Path) -> Path:
    lines = []
    for idx, seg in enumerate(subtitles, 1):
        start = max(seg.start_time_sec - clip_start, 0)
        end = max(seg.end_time_sec - clip_start, start + 0.5)
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(seg.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _video_scale_filter(resolution: str, aspect_ratio: str) -> str:
    """
    Build ffmpeg scale+pad filter for target resolution and aspect ratio.
    Uses letterbox/pillarbox approach - no cropping, adds black bars where needed.
    """
    if resolution == "1080p":
        if aspect_ratio == "9:16":
            return "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"
        elif aspect_ratio == "1:1":
            return "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"
        else:  # 16:9
            return "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"
    else:  # 720p
        if aspect_ratio == "9:16":
            return "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"
        elif aspect_ratio == "1:1":
            return "scale=720:720:force_original_aspect_ratio=decrease,pad=720:720:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"
        else:  # 16:9
            return "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,setsar=1:1"


def render_export(
    db: Session,
    export_job: ExportJob,
    use_brand_kit: bool = True,
    use_ai_dub: bool = True,
    bgm_path: Optional[str] = None,
) -> ExportJob:
    """
    Render clip to MP4 using ffmpeg: cut, scale, overlay subtitles/brand, mix audio + dub.
    """
    clip = export_job.clip
    video = clip.batch.video
    if not video.file_path:
        raise RuntimeError("Video file missing for export")

    output_dir = Path(settings.media_root) / "clips" / str(clip.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Prepare subtitle file
    subs = (
        db.query(SubtitleSegment)
        .filter(SubtitleSegment.clip_id == clip.id)
        .order_by(SubtitleSegment.start_time_sec)
        .all()
    )
    srt_path = _write_srt(subs, clip_start=clip.start_time_sec, path=tmp_dir / "subs.srt")

    # Optional dub audio
    dub_path = None
    if use_ai_dub:
        dub_path = dubbing.synthesize_dub(db, clip, language=clip.language)
        export_job.progress = 30.0
        db.commit()

    # Brand overlay
    logo_path = None
    if use_brand_kit and video.user and video.user.brand_kit and video.user.brand_kit.logo_path:
        candidate = Path(video.user.brand_kit.logo_path)
        if candidate.exists():
            logo_path = str(candidate)

    # Build ffmpeg command
    inputs = []
    filter_complex_parts = []
    map_v = "[vout]"
    map_a = "[aout]"

    inputs.extend(["-ss", str(clip.start_time_sec), "-t", str(clip.duration_sec), "-i", video.file_path])
    input_index = 1
    if dub_path:
        inputs.extend(["-i", dub_path])
        dub_idx = input_index
        input_index += 1
    else:
        dub_idx = None
    if bgm_path:
        inputs.extend(["-i", bgm_path])
        bgm_idx = input_index
        input_index += 1
    elif clip.audio_config and clip.audio_config.bgm_track_id:
        inputs.extend(["-i", clip.audio_config.bgm_track_id])
        bgm_idx = input_index
        input_index += 1
    else:
        bgm_idx = None
    if logo_path:
        inputs.extend(["-i", logo_path])
        logo_idx = input_index
        input_index += 1
    else:
        logo_idx = None

    scale_filter = _video_scale_filter(export_job.resolution, export_job.aspect_ratio)
    if logo_idx is not None:
        video_chain = (
            f"[0:v]{scale_filter},subtitles='{srt_path.as_posix()}'[subbed];"
            f"[subbed][{logo_idx}:v]overlay=W-w-40:H-h-40[vout]"
        )
    else:
        video_chain = f"[0:v]{scale_filter},subtitles='{srt_path.as_posix()}'[vout]"
    filter_complex_parts.append(video_chain)

    audio_inputs = ["[0:a]"]
    if dub_idx is not None:
        audio_inputs.append(f"[{dub_idx}:a]")
    if bgm_idx is not None:
        audio_inputs.append(f"[{bgm_idx}:a]")

    if len(audio_inputs) == 1:
        filter_complex_parts.append(f"{audio_inputs[0]}volume={clip.audio_config.original_volume if clip.audio_config else 1.0}[aout]")
    else:
        # Apply sidechaincompress to duck BGM when voice present.
        if bgm_idx is not None and len(audio_inputs) >= 2:
            # Assume first input is original audio
            bgm_vol = clip.audio_config.bgm_volume if clip.audio_config else 0.25
            mix = (
                f"[{bgm_idx}:a]volume={bgm_vol}[bgm];"
                f"[0:a][bgm]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=250,"
                f"amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
        else:
            mix = f"{''.join(audio_inputs)}amix=inputs={len(audio_inputs)}:duration=first:dropout_transition=0[aout]"
        filter_complex_parts.append(mix)

    output_path = output_dir / f"{export_job.id}.mp4"
    export_fps = export_job.fps or int(utils.probe_fps(video.file_path) or 30)

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filter_complex_parts),
        "-map",
        map_v,
        "-map",
        map_a,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-r",
        str(export_fps),
        "-shortest",
        str(output_path),
    ]
    code, _, err = utils.run_cmd(cmd)
    if code != 0:
        logger.error("export.ffmpeg_failed", error=err)
        export_job.status = "failed"
        export_job.error_message = err
    else:
        try:
            relative = output_path.relative_to(Path(settings.media_root))
            export_job.output_path = f"{settings.media_base_url}/{relative.as_posix()}"
        except Exception:
            export_job.output_path = str(output_path)
        export_job.status = "completed"
        export_job.progress = 100.0
        export_job.clip.status = "exported"
    db.commit()
    logger.info("export.completed", export_id=export_job.id, path=export_job.output_path)
    return export_job
