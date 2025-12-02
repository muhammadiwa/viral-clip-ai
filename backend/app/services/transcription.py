from pathlib import Path
from typing import List, Optional, Tuple

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AIUsageLog, VideoSource, TranscriptSegment
from app.services import utils

logger = structlog.get_logger()
settings = get_settings()


def _chunk_ranges(duration: float, chunk_size: float = 600.0) -> List[Tuple[float, float]]:
    ranges: List[Tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(start + chunk_size, duration)
        ranges.append((start, end - start))
        start = end
    return ranges


def _segment_value(segment, attr: str, default: float | str = ""):
    if isinstance(segment, dict):
        return segment.get(attr, default)
    return getattr(segment, attr, default)


def _transcribe_chunk(client, audio_path: str, model: str) -> Tuple[List[dict], Optional[dict]]:
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(model=model, file=f, response_format="verbose_json")
    raw_segments = getattr(resp, "segments", None) or []
    usage = getattr(resp, "usage", None)
    usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else None
    return raw_segments, usage_dict


def transcribe_video(
    db: Session,
    video: VideoSource,
    progress_callback: callable = None,
) -> List[TranscriptSegment]:
    """
    Extract audio via ffmpeg, chunk if long, and transcribe using OpenAI Whisper.
    
    Args:
        db: Database session
        video: Video to transcribe
        progress_callback: Optional callback(chunk_num, total_chunks, message)
    """
    if not video.file_path:
        raise ValueError("Video file_path missing for transcription")
    if not settings.openai_api_key:
        logger.warning("transcription.no_api_key", msg="OPENAI_API_KEY not configured, using stub transcript")
        # fallback stub
        stub = [
            (0.0, 18.0, "Welcome back, today we dive into viral storytelling."),
            (18.0, 42.0, "Here is the spicy hook that keeps people watching."),
            (42.0, 68.0, "We wrap with a clear takeaway and call to action."),
        ]
        db.query(TranscriptSegment).filter(TranscriptSegment.video_source_id == video.id).delete()
        segments = []
        for start, end, text in stub:
            seg = TranscriptSegment(
                video_source_id=video.id,
                start_time_sec=start,
                end_time_sec=end,
                text=text,
                language="en",
            )
            segments.append(seg)
            db.add(seg)
        video.duration_seconds = stub[-1][1]
        db.commit()
        return segments

    logger.info("transcription.start", video_id=video.id)
    client = utils.get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client not available")

    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    if duration <= 0:
        raise RuntimeError("Cannot determine video duration for transcription")

    audio_root = Path(settings.media_root) / "audio" / "extracted"
    utils.ensure_dir(audio_root)

    all_segments: List[TranscriptSegment] = []
    total_tokens_in = 0
    total_tokens_out = 0
    chunk_ranges = _chunk_ranges(duration)
    total_chunks = len(chunk_ranges)

    for chunk_idx, (start, chunk_dur) in enumerate(chunk_ranges, 1):
        chunk_path = audio_root / f"video-{video.id}-{int(start)}.wav"
        logger.info(
            "transcription.chunk_start",
            video_id=video.id,
            chunk=chunk_idx,
            total_chunks=total_chunks,
            start_sec=start,
            duration_sec=chunk_dur,
        )
        
        # Report progress
        if progress_callback:
            progress_callback(chunk_idx, total_chunks, f"Processing chunk {chunk_idx}/{total_chunks}")

        if not utils.extract_audio(video.file_path, str(chunk_path), start=start, duration=chunk_dur):
            logger.warning("transcription.chunk_audio_failed", video_id=video.id, chunk=chunk_idx)
            continue

        try:
            raw_segments, usage = _transcribe_chunk(client, str(chunk_path), settings.openai_whisper_model)
        except Exception as e:
            logger.error("transcription.chunk_failed", video_id=video.id, chunk=chunk_idx, error=str(e))
            continue

        chunk_tokens_in = 0
        chunk_tokens_out = 0
        if usage:
            chunk_tokens_in = usage.get("prompt_tokens", 0) or 0
            chunk_tokens_out = usage.get("completion_tokens", 0) or 0
            total_tokens_in += chunk_tokens_in
            total_tokens_out += chunk_tokens_out

        # Log per-chunk AIUsageLog for detailed tracking
        if chunk_tokens_in or chunk_tokens_out:
            db.add(
                AIUsageLog(
                    user_id=video.user_id,
                    provider="openai",
                    model=settings.openai_whisper_model,
                    tokens_input=chunk_tokens_in,
                    tokens_output=chunk_tokens_out,
                )
            )

        for seg in raw_segments:
            all_segments.append(
                TranscriptSegment(
                    video_source_id=video.id,
                    start_time_sec=float(_segment_value(seg, "start", 0.0)) + start,
                    end_time_sec=float(_segment_value(seg, "end", 0.0)) + start,
                    text=str(_segment_value(seg, "text", "")).strip(),
                    speaker=None,
                    language=_segment_value(seg, "language", "en") or "en",
                )
            )

        logger.info(
            "transcription.chunk_done",
            video_id=video.id,
            chunk=chunk_idx,
            segments_count=len(raw_segments),
            tokens_in=chunk_tokens_in,
            tokens_out=chunk_tokens_out,
        )

    if not all_segments:
        raise RuntimeError("Transcription produced no segments")

    video.duration_seconds = max(seg.end_time_sec for seg in all_segments)

    db.query(TranscriptSegment).filter(TranscriptSegment.video_source_id == video.id).delete()
    for seg in all_segments:
        db.add(seg)
    db.commit()
    db.refresh(video)

    logger.info(
        "transcription.done",
        video_id=video.id,
        segments=len(all_segments),
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
    )
    return all_segments
