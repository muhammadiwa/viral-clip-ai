import os
import uuid
from typing import Any, Dict

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, ProcessingJob, User
from app.services import utils

try:
    from yt_dlp import YoutubeDL
except Exception:  # pragma: no cover
    YoutubeDL = None

settings = get_settings()


async def create_from_youtube(
    db: Session,
    user: User,
    youtube_url: str,
    video_type: str,
    aspect_ratio: str,
    clip_length_preset: str,
    subtitle: bool,
) -> tuple[VideoSource, ProcessingJob]:
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "videos", str(user.id))
    os.makedirs(user_dir, exist_ok=True)

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

    # Download highest quality mp4 via yt_dlp.
    if YoutubeDL is None:
        raise RuntimeError("yt_dlp not installed; cannot download YouTube video")
    target_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": target_path,
        "merge_output_format": "mp4",
        "quiet": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if info and info.get("title"):
                video.title = info.get("title")
            ydl.download([youtube_url])
        video.file_path = target_path
        duration = utils.probe_duration(target_path)
        if duration:
            video.duration_seconds = duration
        db.commit()
    except Exception as exc:
        video.status = "failed"
        video.error_message = str(exc)
        db.commit()
        raise

    payload: Dict[str, Any] = {
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "clip_length_preset": clip_length_preset,
        "subtitle": subtitle,
    }
    job = ProcessingJob(
        video_source_id=video.id,
        job_type="transcription_and_segmentation",
        payload=payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return video, job


async def create_from_upload(
    db: Session,
    user: User,
    upload_file: UploadFile,
    video_type: str,
    aspect_ratio: str,
    clip_length_preset: str,
    subtitle: bool,
) -> tuple[VideoSource, ProcessingJob]:
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "videos", str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    if upload_file.content_type and not upload_file.content_type.startswith("video/"):
        raise RuntimeError("Only video uploads are allowed")
    # Best-effort size guard (fastapi may not expose size for streaming clients).
    upload_file.file.seek(0, os.SEEK_END)
    size_mb = upload_file.file.tell() / (1024 * 1024)
    upload_file.file.seek(0)
    if size_mb > 2048:  # 2GB guardrail
        raise RuntimeError("Uploaded file too large (max 2GB)")

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
    duration = utils.probe_duration(file_path)
    if duration:
        video.duration_seconds = duration
        db.commit()

    payload: Dict[str, Any] = {
        "video_type": video_type,
        "aspect_ratio": aspect_ratio,
        "clip_length_preset": clip_length_preset,
        "subtitle": subtitle,
    }
    job = ProcessingJob(
        video_source_id=video.id,
        job_type="transcription_and_segmentation",
        payload=payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return video, job
