from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, get_current_user, enforce_daily_job_limit, enforce_credits
from app.core.config import get_settings
from app.models import VideoSource, ClipBatch, ProcessingJob, User
from app.schemas import ClipBatchCreate, ClipBatchOut, ClipBatchWithJob

settings = get_settings()
router = APIRouter(prefix="/viral-clip", tags=["clip_batches"])


@router.post("/videos/{video_id}/clip-batches", response_model=ClipBatchWithJob)
def create_clip_batch(
    video_id: int,
    payload: ClipBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = (
        db.query(VideoSource).filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id).first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Simple credit consumption: 1 credit per minute of video (min 1).
    video_duration = video.duration_seconds or 0
    credits_needed = max(
        settings.credit_cost_per_minute,
        int(video_duration // 60) * settings.credit_cost_per_minute or settings.credit_cost_per_minute,
    )
    enforce_credits(db, current_user, credits_needed)
    # Rate limit per-day clip batch creation
    enforce_daily_job_limit(db, current_user)

    config_json = payload.model_dump()
    batch = ClipBatch(
        video_source_id=video.id,
        name=f"batch-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        status="processing",
        config_json=config_json,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    job = ProcessingJob(
        video_source_id=video.id,
        job_type="clip_generation",
        payload={"clip_batch_id": batch.id, **config_json},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {"batch": batch, "job": job}


@router.get("/videos/{video_id}/clip-batches", response_model=list[ClipBatchOut])
def list_clip_batches(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = (
        db.query(VideoSource).filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id).first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    batches = (
        db.query(ClipBatch)
        .filter(ClipBatch.video_source_id == video.id)
        .order_by(ClipBatch.created_at.desc())
        .all()
    )
    return batches
