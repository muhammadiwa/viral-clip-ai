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
        raise HTTPException(status_code=400, detail="Clip video not ready")
    
    # Resolve local path from URL or absolute path
    if clip.video_path.startswith("http"):
        rel = clip.video_path.replace(settings.media_base_url + "/", "")
        local_path = Path(settings.media_root) / rel
    else:
        local_path = Path(clip.video_path)
    
    if not local_path.exists():
        raise HTTPException(status_code=404, detail="Clip file missing on server")
    
    return FileResponse(
        local_path,
        filename=f"clip-{clip.id}-{clip.title or 'video'}.mp4",
        media_type="video/mp4",
    )
