import json
from pathlib import Path
from typing import List, Optional

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ClipBatch,
    Clip,
    ClipLLMContext,
    TranscriptSegment,
    SceneSegment,
    AIUsageLog,
)
from app.services import utils

logger = structlog.get_logger()
settings = get_settings()


def _target_duration(preset: str) -> float:
    mapping = {
        "auto_0_60": 50.0,
        "0_30": 25.0,
        "0_90": 75.0,
    }
    return mapping.get(preset, 50.0)


def _build_prompt(config: dict, transcripts: List[TranscriptSegment], scenes: List[SceneSegment]) -> str:
    transcript_text = " ".join(t.text for t in transcripts)[:3500]
    top_scenes = scenes[:8]
    scene_spans = ", ".join([f"{round(s.start_time_sec,1)}-{round(s.end_time_sec,1)}" for s in top_scenes])
    return (
        "You are an expert viral video editor. Combine adjacent scenes when needed to hit target duration "
        f"({config.get('clip_length_preset')} => around {_target_duration(config.get('clip_length_preset','auto_0_60'))}s). "
        f"Video type: {config.get('video_type')}, aspect ratio target: {config.get('aspect_ratio')}. "
        f"Candidate scene spans (seconds): {scene_spans}. "
        "Return JSON with key 'clips' (8-12 items). Each clip object: "
        "{start_sec, end_sec, title, description, viral_score (0-10), grades: {hook, flow, value, trend}}. "
        "Prefer strongest hooks in the first 5 seconds. Ensure start/end strictly increasing and within provided scene bounds. "
        "Transcript context:\n"
        f"{transcript_text}"
    )


def _parse_response_text(resp_text: str) -> List[dict]:
    try:
        data = json.loads(resp_text)
        return data.get("clips", [])
    except Exception as e:
        logger.error("virality.parse_failed", error=str(e))
        return []


def generate_clips_for_batch(
    db: Session,
    batch: ClipBatch,
    config: dict,
) -> List[Clip]:
    """
    Use OpenAI Responses API to score and propose viral clips based on transcript + scene windows.
    """
    if not settings.openai_api_key:
        logger.warning("virality.no_api_key", msg="OPENAI_API_KEY not configured, using scene fallback")
        client = None
    else:
        client = utils.get_openai_client()
        if client is None:
            logger.warning("virality.no_client", msg="OpenAI client unavailable, using scene fallback")

    logger.info("virality.start", batch_id=batch.id)
    target_duration = _target_duration(config.get("clip_length_preset", "auto_0_60"))
    timeframe_start = config.get("processing_timeframe_start") or 0.0
    timeframe_end = config.get("processing_timeframe_end")

    scenes = (
        db.query(SceneSegment)
        .filter(SceneSegment.video_source_id == batch.video_source_id)
        .order_by(SceneSegment.start_time_sec)
        .all()
    )
    transcripts = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_source_id == batch.video_source_id)
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )

    existing_clip_ids = [c.id for c in db.query(Clip).filter(Clip.clip_batch_id == batch.id).all()]
    if existing_clip_ids:
        db.query(ClipLLMContext).filter(ClipLLMContext.clip_id.in_(existing_clip_ids)).delete(
            synchronize_session=False
        )
    db.query(Clip).filter(Clip.clip_batch_id == batch.id).delete(synchronize_session=False)

    prompt = _build_prompt(config, transcripts, scenes)
    clips_json: List[dict] = []
    if client:
        try:
            response = client.responses.create(
                model=settings.openai_responses_model,
                input=prompt,
                response_format={"type": "json_object"},
                temperature=0.4,
            )
            # Extract text payload robustly
            text_out = ""
            if getattr(response, "output", None):
                try:
                    text_out = response.output[0].content[0].text  # type: ignore[attr-defined]
                except Exception:
                    text_out = ""
            if not text_out and getattr(response, "choices", None):
                text_out = response.choices[0].message.content  # type: ignore[attr-defined]
            if not text_out:
                text_out = getattr(response, "response_text", None) or ""
            clips_json = _parse_response_text(text_out)
        except Exception as exc:
            logger.error("virality.llm_failed", error=str(exc))
            clips_json = []

    clips: List[Clip] = []
    if clips_json:
        for idx, clip_obj in enumerate(clips_json):
            start = float(clip_obj.get("start_sec", 0.0))
            end = float(clip_obj.get("end_sec", start + target_duration))
            if timeframe_end and end > timeframe_end:
                end = timeframe_end
            if start < timeframe_start:
                start = timeframe_start
            if end <= start:
                continue
            duration = end - start
            clip = Clip(
                clip_batch_id=batch.id,
                start_time_sec=start,
                end_time_sec=end,
                duration_sec=duration,
                title=clip_obj.get("title") or f"Viral moment #{idx+1}",
                description=clip_obj.get("description"),
                viral_score=float(clip_obj.get("viral_score", 0.0)),
                grade_hook=clip_obj.get("grades", {}).get("hook"),
                grade_flow=clip_obj.get("grades", {}).get("flow"),
                grade_value=clip_obj.get("grades", {}).get("value"),
                grade_trend=clip_obj.get("grades", {}).get("trend"),
                language=config.get("language") or "en",
                status="candidate",
            )
            db.add(clip)
            clips.append(clip)
    else:
        # Fallback: build clips from scenes if LLM fails
        for idx, scene in enumerate(scenes):
            start = max(scene.start_time_sec, timeframe_start)
            end = min(scene.end_time_sec, timeframe_end) if timeframe_end else scene.end_time_sec
            if end <= start:
                continue
            duration = min(target_duration, end - start)
            clip = Clip(
                clip_batch_id=batch.id,
                start_time_sec=start,
                end_time_sec=start + duration,
                duration_sec=duration,
                title=f"Scene highlight #{idx+1}",
                description="Auto fallback clip from scene segmentation.",
                viral_score=6.0,
                grade_hook="B",
                grade_flow="B",
                grade_value="B",
                grade_trend="B",
                language=config.get("language") or "en",
                status="candidate",
            )
            db.add(clip)
            clips.append(clip)
    db.commit()

    # Thumbnail rendering
    for clip in clips:
        thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / str(clip.id))
        thumb_path = thumb_dir / "thumb.jpg"
        mid = clip.start_time_sec + (clip.duration_sec / 2)
        if batch.video.file_path:
            utils.render_thumbnail(batch.video.file_path, str(thumb_path), mid)
            try:
                relative = thumb_path.relative_to(Path(settings.media_root))
                clip.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
            except Exception:
                clip.thumbnail_path = str(thumb_path)
        db.add(
            ClipLLMContext(
                clip_id=clip.id,
                prompt=prompt,
                response_json=clips_json,
            )
        )
    db.commit()

    usage = getattr(response, "usage", None)
    if usage:
        db.add(
            AIUsageLog(
                user_id=batch.video.user_id,
                provider="openai",
                model=settings.openai_responses_model,
                tokens_input=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_output=getattr(usage, "completion_tokens", 0) or 0,
            )
        )
        db.commit()

    batch.status = "ready" if clips else "failed"
    db.commit()
    logger.info("virality.done", batch_id=batch.id, clips=len(clips))
    return clips
