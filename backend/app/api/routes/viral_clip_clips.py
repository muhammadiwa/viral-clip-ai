from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.models import ClipBatch, Clip, TranscriptSegment, User
from app.schemas import ClipOut, ClipDetailOut

settings = get_settings()

router = APIRouter(prefix="/viral-clip", tags=["clips"])


@router.get("/videos/{video_id}/clips")
def list_video_clips(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all clips for a video (from all batches), sorted by created_at descending."""
    from app.models import VideoSource
    
    video = (
        db.query(VideoSource)
        .filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    clips = (
        db.query(Clip)
        .join(ClipBatch)
        .filter(ClipBatch.video_source_id == video_id)
        .order_by(Clip.created_at.desc())
        .all()
    )
    
    # Add aspect_ratio from batch config to each clip
    result = []
    for clip in clips:
        clip_data = ClipOut.model_validate(clip).model_dump()
        # Get aspect_ratio from batch config
        if clip.batch and clip.batch.config_json:
            clip_data["aspect_ratio"] = clip.batch.config_json.get("aspect_ratio", "16:9")
        else:
            clip_data["aspect_ratio"] = "16:9"
        result.append(clip_data)
    
    return result


@router.get("/clip-batches/{batch_id}/clips", response_model=list[ClipOut])
def list_clips(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = (
        db.query(ClipBatch)
        .filter(ClipBatch.id == batch_id, ClipBatch.video.has(user_id=current_user.id))
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    clips = (
        db.query(Clip)
        .filter(Clip.clip_batch_id == batch.id)
        .order_by(Clip.viral_score.desc().nullslast(), Clip.created_at.desc())
        .all()
    )
    return clips


@router.get("/clips/{clip_id}", response_model=ClipDetailOut)
def get_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")

    transcript = (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.video_source_id == clip.batch.video_source_id,
            TranscriptSegment.start_time_sec >= clip.start_time_sec,
            TranscriptSegment.end_time_sec <= clip.end_time_sec,
        )
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )
    transcript_preview = " ".join([t.text for t in transcript])[:400]
    
    # Get hashtags and hook_text from LLM context
    hashtags = ["viral", "trending", "fyp"]
    hook_text = ""
    detected_video_type = "unknown"
    
    if clip.llm_context and clip.llm_context.response_json:
        response_json = clip.llm_context.response_json
        hashtags = response_json.get("hashtags", hashtags)
        hook_text = response_json.get("hook_text", "")
        detected_video_type = response_json.get("detected_video_type", "unknown")
    
    clip_data = ClipOut.model_validate(clip).model_dump()
    return ClipDetailOut(
        **clip_data,
        video_source_id=clip.batch.video_source_id,
        transcript_preview=transcript_preview,
        subtitle_language=clip.language,
        viral_breakdown={
            "hook": clip.grade_hook,
            "flow": clip.grade_flow,
            "value": clip.grade_value,
            "trend": clip.grade_trend,
        },
        hashtags=hashtags,
        hook_text=hook_text,
        detected_video_type=detected_video_type,
    )


@router.get("/clips/{clip_id}/download")
def download_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the auto-generated clip video file."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    if not clip.video_path:
        raise HTTPException(status_code=400, detail="Clip video not ready. Please wait for processing to complete.")
    
    # Resolve local path from URL or absolute path
    if clip.video_path.startswith("http"):
        rel = clip.video_path.replace(settings.media_base_url + "/", "")
        local_path = Path(settings.media_root) / rel
    else:
        local_path = Path(clip.video_path)
    
    if not local_path.exists():
        raise HTTPException(status_code=404, detail=f"Clip file missing on server. Expected path: {local_path}")
    
    # Create safe filename from clip title
    safe_title = "".join(c for c in (clip.title or "clip") if c.isalnum() or c in " -_")[:40]
    filename = f"{safe_title}-{clip.id}.mp4"
    
    return FileResponse(
        path=local_path,
        filename=filename,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
    )


@router.post("/clips/{clip_id}/regenerate-hashtags")
def regenerate_hashtags(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate hashtags for a clip using AI."""
    from app.services.virality import _generate_hashtags_with_llm
    
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    # Get transcript for this clip
    transcript = (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.video_source_id == clip.batch.video_source_id,
            TranscriptSegment.start_time_sec >= clip.start_time_sec,
            TranscriptSegment.end_time_sec <= clip.end_time_sec,
        )
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )
    transcript_text = " ".join([t.text for t in transcript])
    
    # Get video type from existing context
    video_type = "unknown"
    if clip.llm_context and clip.llm_context.response_json:
        video_type = clip.llm_context.response_json.get("detected_video_type", "unknown")
    
    # Generate new hashtags
    new_hashtags = _generate_hashtags_with_llm(
        transcript_text, clip.title or "", video_type
    )
    
    # Update LLM context
    if clip.llm_context:
        response_json = clip.llm_context.response_json or {}
        response_json["hashtags"] = new_hashtags
        clip.llm_context.response_json = response_json
        db.commit()
    
    return {"hashtags": new_hashtags, "message": "Hashtags regenerated successfully"}
