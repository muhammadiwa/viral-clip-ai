import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import structlog
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, ProcessingJob, User
from app.services import utils

try:
    from yt_dlp import YoutubeDL
except Exception:  # pragma: no cover
    YoutubeDL = None

logger = structlog.get_logger()
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

    # Download highest quality mp4 via yt_dlp with retry logic.
    if YoutubeDL is None:
        raise RuntimeError("yt_dlp not installed; cannot download YouTube video")
    target_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": target_path,
        "merge_output_format": "mp4",
        "quiet": True,
    }

    max_retries = settings.youtube_download_retries
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("youtube.download_attempt", attempt=attempt, max_retries=max_retries, url=youtube_url)
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                if info:
                    if info.get("title"):
                        video.title = info.get("title")
                    # Get YouTube thumbnail URL (highest quality available)
                    thumbnail_url = info.get("thumbnail")
                    if not thumbnail_url:
                        # Try to get from thumbnails list
                        thumbnails = info.get("thumbnails", [])
                        if thumbnails:
                            # Get highest resolution thumbnail
                            best_thumb = max(thumbnails, key=lambda t: t.get("height", 0) or 0)
                            thumbnail_url = best_thumb.get("url")
                    if thumbnail_url:
                        video.thumbnail_path = thumbnail_url
                        logger.info("youtube.thumbnail_found", thumbnail_url=thumbnail_url)
                ydl.download([youtube_url])
            video.file_path = target_path
            duration = utils.probe_duration(target_path)
            if duration:
                video.duration_seconds = duration
            
            db.commit()
            logger.info("youtube.download_success", video_id=video.id, attempt=attempt)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logger.warning("youtube.download_failed", attempt=attempt, error=str(exc))
            if attempt < max_retries:
                time.sleep(settings.retry_delay_seconds)
            else:
                video.status = "failed"
                video.error_message = f"Failed after {max_retries} attempts: {str(exc)}"
                db.commit()

    if last_error:
        raise last_error

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

    # Validate content type
    content_type = upload_file.content_type or ""
    allowed_types = settings.allowed_video_types_list
    if content_type and content_type not in allowed_types and not content_type.startswith("video/"):
        raise RuntimeError(f"Invalid file type. Allowed: {', '.join(allowed_types)}")

    # Best-effort size guard (fastapi may not expose size for streaming clients).
    upload_file.file.seek(0, os.SEEK_END)
    size_mb = upload_file.file.tell() / (1024 * 1024)
    upload_file.file.seek(0)
    max_size = settings.max_upload_size_mb
    if size_mb > max_size:
        raise RuntimeError(f"Uploaded file too large (max {max_size}MB)")

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
    
    # Generate thumbnail at 10% of video duration
    thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / "videos" / str(video.id))
    thumb_path = thumb_dir / "thumb.jpg"
    thumb_timestamp = (duration or 10) * 0.1  # 10% into video
    if utils.render_thumbnail(file_path, str(thumb_path), thumb_timestamp):
        try:
            relative = thumb_path.relative_to(Path(settings.media_root))
            video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
        except Exception:
            video.thumbnail_path = str(thumb_path)
    
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
