from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import VideoSource, User
from app.schemas import VideoSourceBase
from app.services import video_ingest

router = APIRouter(prefix="/viral-clip", tags=["viral-clip"])


@router.post("/video/youtube", response_model=VideoSourceBase)
async def create_video_from_youtube(
    youtube_url: str = Form(...),
    video_type: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_length_preset: str = Form("auto_0_60"),
    subtitle: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await video_ingest.create_from_youtube(
        db=db,
        user=current_user,
        youtube_url=youtube_url,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        clip_length_preset=clip_length_preset,
        subtitle=subtitle,
    )
    return video


@router.post("/video/upload", response_model=VideoSourceBase)
async def create_video_from_upload(
    file: UploadFile = File(...),
    video_type: str = Form("podcast"),
    aspect_ratio: str = Form("9:16"),
    clip_length_preset: str = Form("auto_0_60"),
    subtitle: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = await video_ingest.create_from_upload(
        db=db,
        user=current_user,
        upload_file=file,
        video_type=video_type,
        aspect_ratio=aspect_ratio,
        clip_length_preset=clip_length_preset,
        subtitle=subtitle,
    )
    return video


@router.get("/videos", response_model=List[VideoSourceBase])
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
