from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_db, get_current_user, enforce_daily_job_limit, enforce_credits
from app.core.config import get_settings
from app.models import Clip, ClipBatch, ExportJob, ProcessingJob, User
from app.schemas import ExportCreate, ExportOut, ExportWithJob

router = APIRouter(tags=["exports"])


@router.post("/viral-clip/clips/{clip_id}/exports", response_model=ExportWithJob)
def create_export(
    clip_id: int,
    payload: ExportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    enforce_daily_job_limit(db, current_user)
    enforce_credits(db, current_user, get_settings().credit_cost_per_export)

    export = ExportJob(
        clip_id=clip.id,
        resolution=payload.resolution,
        fps=payload.fps,
        aspect_ratio=payload.aspect_ratio,
        status="queued",
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    job = ProcessingJob(
        video_source_id=clip.batch.video_source_id,
        job_type="export_clip",
        payload={
            "export_id": export.id,
            "clip_id": clip.id,
            "use_brand_kit": payload.use_brand_kit,
            "use_ai_dub": payload.use_ai_dub,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"export": export, "job": job}


@router.get("/exports/{export_id}", response_model=ExportOut)
def get_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export = db.query(ExportJob).filter(ExportJob.id == export_id).first()
    if not export or export.clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    return export


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    export = db.query(ExportJob).filter(ExportJob.id == export_id).first()
    if not export or export.clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    if not export.output_path:
        raise HTTPException(status_code=400, detail="Export not ready")
    settings = get_settings()
    if export.output_path.startswith("http"):
        rel = export.output_path.replace(settings.media_base_url + "/", "")
        local_path = Path(settings.media_root) / rel
    else:
        local_path = Path(export.output_path)
    if not local_path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(local_path, filename=f"clip-{export.clip_id}-{export.id}.mp4")


@router.get("/viral-clip/clips/{clip_id}/exports", response_model=list[ExportOut])
def list_exports(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    return db.query(ExportJob).filter(ExportJob.clip_id == clip.id).order_by(ExportJob.created_at.desc()).all()


@router.get("/viral-clip/clip-batches/{batch_id}/exports", response_model=dict[int, list[ExportOut]])
def list_exports_for_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = (
        db.query(ClipBatch)
        .options(selectinload(ClipBatch.clips), joinedload(ClipBatch.video))
        .filter(ClipBatch.id == batch_id)
        .first()
    )
    if not batch or not batch.video or batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip batch not found")
    clip_ids = [clip.id for clip in batch.clips]
    if not clip_ids:
        return {}
    exports = (
        db.query(ExportJob)
        .filter(ExportJob.clip_id.in_(clip_ids))
        .order_by(ExportJob.created_at.desc())
        .all()
    )
    result: dict[int, list[ExportJob]] = {clip_id: [] for clip_id in clip_ids}
    for export in exports:
        result.setdefault(export.clip_id, []).append(export)
    return result
