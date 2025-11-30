import json
import re
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


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")].strip()
    return cleaned


def _coerce_json_payload(resp_text: str) -> str:
    candidate = _strip_code_fences(resp_text)
    if not candidate:
        return ""
    if candidate[0] not in "[{":
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start : end + 1]
    return candidate


def _parse_response_text(resp_text: str) -> List[dict]:
    payload = _coerce_json_payload(resp_text)
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except Exception as e:  # pragma: no cover - defensive logging
        logger.error("virality.parse_failed", error=str(e), preview=payload[:200])
        return []
    if isinstance(data, dict):
        clips = data.get("clips", [])
        return clips if isinstance(clips, list) else []
    if isinstance(data, list):
        return data
    return []


def _response_text_from_openai(response) -> str:
    if response is None:
        return ""
    chunks: List[str] = []
    output = getattr(response, "output", None)
    if output:
        for item in output:
            for content in getattr(item, "content", []) or []:
                text_obj = getattr(content, "text", None)
                if text_obj and getattr(text_obj, "value", None):
                    chunks.append(text_obj.value)
                elif getattr(content, "value", None):
                    chunks.append(content.value)
    if not chunks:
        textual = getattr(response, "output_text", None)
        if textual:
            chunks.append(textual)
    if not chunks and getattr(response, "choices", None):
        choice0 = response.choices[0]
        message = getattr(choice0, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if isinstance(content, list):
                for part in content:
                    text_val = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                    if text_val:
                        chunks.append(text_val if isinstance(text_val, str) else str(text_val))
            elif content:
                chunks.append(content if isinstance(content, str) else str(content))
        text_attr = getattr(choice0, "text", None)
        if text_attr:
            chunks.append(text_attr)
    if not chunks and getattr(response, "response_text", None):
        chunks.append(response.response_text)
    return "\n".join([chunk for chunk in chunks if chunk]).strip()


def generate_clips_for_batch(
    db: Session,
    batch: ClipBatch,
    config: dict,
) -> tuple[List[Clip], dict]:
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
    response = None
    response_text = ""
    if client:
        try:
            response = client.responses.create(
                model=settings.openai_responses_model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "You are an expert viral video editor. Respond using ONLY valid JSON and no commentary.",
                            }
                        ],
                    },
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                ],
                temperature=0.4,
            )
            response_text = _response_text_from_openai(response)
            if not response_text:
                logger.error("virality.empty_response", batch_id=batch.id)
            clips_json = _parse_response_text(response_text)
        except Exception as exc:
            logger.error("virality.llm_failed", error=str(exc))
            clips_json = []

    clips: List[Clip] = []
    llm_used = bool(clips_json)
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
                response_json={"clips": clips_json, "raw_text": response_text[:2000]},
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
    logger.info("virality.done", batch_id=batch.id, clips=len(clips), llm_used=llm_used)
    metadata = {
        "llm_used": llm_used,
        "clip_count": len(clips),
        "fallback": None if llm_used else "scene",
    }
    return clips, metadata
