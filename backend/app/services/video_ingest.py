import os
import uuid
from typing import Any, Dict

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, ProcessingJob, User

settings = get_settings()


async def create_from_youtube(
    db: Session,
    user: User,
    youtube_url: str,
    video_type: str,
    aspect_ratio: str,
    clip_length_preset: str,
    subtitle: bool,
) -> VideoSource:
    video = VideoSource(
        user_id=user.id,
        source_type="youtube",
        source_url=youtube_url,
        title=youtube_url,
        status="pending",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    payload: Dict[str, Any] = {
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "clip_length_preset": clip_length_preset,
        "subtitle": subtitle,
    }
    job = ProcessingJob(video_source_id=video.id, job_type="transcription_and_clipping", payload=payload)
    db.add(job)
    db.commit()
    return video


async def create_from_upload(
    db: Session,
    user: User,
    upload_file: UploadFile,
    video_type: str,
    aspect_ratio: str,
    clip_length_preset: str,
    subtitle: bool,
) -> VideoSource:
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "videos", str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    ext = os.path.splitext(upload_file.filename or "")[1] or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(user_dir, filename)

    with open(file_path, "wb") as f:
        f.write(await upload_file.read())

    video = VideoSource(
        user_id=user.id,
        source_type="upload",
        file_path=file_path,
        title=upload_file.filename,
        status="pending",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    payload: Dict[str, Any] = {
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "clip_length_preset": clip_length_preset,
        "subtitle": subtitle,
    }
    job = ProcessingJob(video_source_id=video.id, job_type="transcription_and_clipping", payload=payload)
    db.add(job)
    db.commit()
    return video
