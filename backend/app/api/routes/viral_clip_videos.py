from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, enforce_daily_job_limit, enforce_credits
from app.models import VideoSource, User, TranscriptSegment, SceneSegment, ProcessingJob
from app.schemas import (
    VideoSourceOut,
    VideoCreateResponse,
    TranscriptSegmentOut,
    SceneSegmentOut,
)
from app.services import video_ingest

router = APIRouter(prefix="/viral-clip", tags=["viral-clip"])


@router.post("/video/youtube", response_model=VideoCreateResponse)
async def create_video_from_youtube(
    youtube_url: str = Form(...),
    video_type: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_length_preset: str = Form("auto_0_60"),
    subtitle: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_daily_job_limit(db, current_user)
    video, job = await video_ingest.create_from_youtube(
        db=db,
        user=current_user,
        youtube_url=youtube_url,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        clip_length_preset=clip_length_preset,
        subtitle=subtitle,
    )
    return {"video": video, "job": job}


@router.post("/video/upload", response_model=VideoCreateResponse)
async def create_video_from_upload(
    file: UploadFile = File(...),
    video_type: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_length_preset: str = Form("auto_0_60"),
    subtitle: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_daily_job_limit(db, current_user)
    video, job = await video_ingest.create_from_upload(
        db=db,
        user=current_user,
        upload_file=file,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        clip_length_preset=clip_length_preset,
        subtitle=subtitle,
    )
    return {"video": video, "job": job}


@router.get("/videos", response_model=List[VideoSourceOut])
def list_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    videos = (
        db.query(VideoSource)
        .filter(VideoSource.user_id == current_user.id)
        .order_by(VideoSource.created_at.desc())
        .all()
    )
    return videos


@router.get("/videos/{video_id}/transcript", response_model=List[TranscriptSegmentOut])
def get_transcript(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = (
        db.query(VideoSource).filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id).first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_source_id == video.id)
        .order_by(TranscriptSegment.start_time_sec)
        .all()
    )
    return segments


@router.get("/videos/{video_id}/scenes", response_model=List[SceneSegmentOut])
def get_scenes(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = (
        db.query(VideoSource).filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id).first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    segments = (
        db.query(SceneSegment)
        .filter(SceneSegment.video_source_id == video.id)
        .order_by(SceneSegment.start_time_sec)
        .all()
    )
    return segments


@router.get("/videos/{video_id}/download")
def download_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = (
        db.query(VideoSource).filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id).first()
    )
    if not video or not video.file_path:
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(video.file_path, filename=f"video-{video.id}.mp4")
