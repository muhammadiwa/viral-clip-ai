from typing import List

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Clip, SubtitleSegment, TranscriptSegment, AIUsageLog
from app.services import utils
from app.services.exporting import _format_timestamp

logger = structlog.get_logger()
settings = get_settings()


def generate_for_clip(db: Session, clip: Clip) -> List[SubtitleSegment]:
    """Generate subtitle segments by slicing transcript to the clip window."""
    logger.info("subtitles.generate", clip_id=clip.id)
    transcript_segments = (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.video_source_id == clip.batch.video_source_id,
            TranscriptSegment.start_time_sec >= clip.start_time_sec,
            TranscriptSegment.end_time_sec <= clip.end_time_sec,
        )
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )

    if not transcript_segments:
        transcript_segments = [
            TranscriptSegment(
                video_source_id=clip.batch.video_source_id,
                start_time_sec=clip.start_time_sec,
                end_time_sec=clip.end_time_sec,
                text=clip.description or clip.title or "Clip content",
                language="en",
            )
        ]

    db.query(SubtitleSegment).filter(SubtitleSegment.clip_id == clip.id).delete()
    subtitles: List[SubtitleSegment] = []
    for seg in transcript_segments:
        subtitles.append(
            SubtitleSegment(
                clip_id=clip.id,
                start_time_sec=seg.start_time_sec,
                end_time_sec=seg.end_time_sec,
                text=seg.text,
                language=seg.language or "en",
            )
        )
    for sub in subtitles:
        db.add(sub)
    db.commit()
    logger.info("subtitles.done", clip_id=clip.id, count=len(subtitles))
    return subtitles


def subtitle_srt_text(db: Session, clip: Clip) -> str:
    subs = (
        db.query(SubtitleSegment)
        .filter(SubtitleSegment.clip_id == clip.id)
        .order_by(SubtitleSegment.start_time_sec)
        .all()
    )
    lines = []
    for idx, seg in enumerate(subs, 1):
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(seg.start_time_sec)} --> {_format_timestamp(seg.end_time_sec)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def translate_subtitles(db: Session, clip: Clip, target_language: str) -> List[SubtitleSegment]:
    """Translate subtitle rows using OpenAI Responses API."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured for translation")
    client = utils.get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client not available")

    base_segments = (
        db.query(SubtitleSegment)
        .filter(SubtitleSegment.clip_id == clip.id)
        .order_by(SubtitleSegment.start_time_sec)
        .all()
    )
    if not base_segments:
        base_segments = generate_for_clip(db, clip)

    prompt = (
        "Translate the following subtitles to language code "
        f"{target_language}. Return JSON array with same length preserving timing. "
        "Fields: start_time_sec, end_time_sec, text."
    )
    content = [{"role": "user", "content": prompt + "\n" + "\n".join([s.text for s in base_segments])}]
    resp = client.responses.create(
        model=settings.openai_responses_model,
        input=prompt + "\n" + "\n".join([f"{s.text}" for s in base_segments]),
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    text_out = ""
    if getattr(resp, "output", None):
        try:
            text_out = resp.output[0].content[0].text  # type: ignore[attr-defined]
        except Exception:
            text_out = ""
    if not text_out and getattr(resp, "choices", None):
        text_out = resp.choices[0].message.content  # type: ignore[attr-defined]
    if not text_out:
        text_out = getattr(resp, "response_text", None) or ""

    import json

    try:
        translated_json = json.loads(text_out).get("subtitles", [])
    except Exception:
        translated_json = []

    db.query(SubtitleSegment).filter(SubtitleSegment.clip_id == clip.id, SubtitleSegment.language == target_language).delete()
    translated: List[SubtitleSegment] = []
    # align count; if missing, fallback to base timing
    if translated_json and len(translated_json) == len(base_segments):
        for base, seg in zip(base_segments, translated_json):
            translated.append(
                SubtitleSegment(
                    clip_id=clip.id,
                    start_time_sec=seg.get("start_time_sec", base.start_time_sec),
                    end_time_sec=seg.get("end_time_sec", base.end_time_sec),
                    text=seg.get("text", base.text),
                    language=target_language,
                )
            )
    else:
        for base in base_segments:
            translated.append(
                SubtitleSegment(
                    clip_id=clip.id,
                    start_time_sec=base.start_time_sec,
                    end_time_sec=base.end_time_sec,
                    text=f"[{target_language}] {base.text}",
                    language=target_language,
                )
            )
    for seg in translated:
        db.add(seg)
    usage = getattr(resp, "usage", None)
    if usage:
        db.add(
            AIUsageLog(
                user_id=clip.batch.video.user_id,
                provider="openai",
                model=settings.openai_responses_model,
                tokens_input=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_output=getattr(usage, "completion_tokens", 0) or 0,
            )
        )
    db.commit()
    logger.info("subtitles.translated", clip_id=clip.id, target_language=target_language, count=len(translated))
    return translated
