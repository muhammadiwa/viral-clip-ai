from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import ProcessingJob, User
from app.schemas import ProcessingJobOut

router = APIRouter(prefix="/viral-clip", tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.video and job.video.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return job
