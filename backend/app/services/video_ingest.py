import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import VideoSource, ProcessingJob, User
from app.services import utils
from app.services.youtube_metadata import youtube_metadata_service, YouTubeMetadataError
from app.services.slug import slug_service

try:
    from yt_dlp import YoutubeDL
except Exception:  # pragma: no cover
    YoutubeDL = None

logger = structlog.get_logger()
settings = get_settings()


def _get_existing_slugs(db: Session) -> List[str]:
    """Get all existing slugs from the database."""
    result = db.query(VideoSource.slug).filter(VideoSource.slug.isnot(None)).all()
    return [row[0] for row in result]


async def create_video_from_youtube_url(
    db: Session,
    user: User,
    youtube_url: str,
) -> VideoSource:
    """
    Create a video record from YouTube URL by fetching metadata only.
    
    This function does NOT download the video file. It only:
    1. Extracts video ID from URL
    2. Fetches metadata via oEmbed API
    3. Creates VideoSource record with is_downloaded=False
    4. Generates a unique slug from the video title
    
    Args:
        db: Database session
        user: User creating the video
        youtube_url: YouTube URL in any supported format
        
    Returns:
        VideoSource with metadata populated, is_downloaded=False
        
    Raises:
        YouTubeMetadataError: If URL is invalid or video is unavailable
    """
    # Fetch metadata from YouTube (no download)
    video_info = await youtube_metadata_service.get_video_info(youtube_url)
    
    # Generate unique slug from title
    base_slug = slug_service.generate_slug(video_info.title)
    existing_slugs = _get_existing_slugs(db)
    unique_slug = slug_service.ensure_unique_slug(base_slug, existing_slugs)
    
    # Create video record with metadata only
    video = VideoSource(
        user_id=user.id,
        source_type="youtube",
        source_url=youtube_url,
        title=video_info.title,
        status="pending",
        youtube_video_id=video_info.video_id,
        youtube_thumbnail_url=video_info.thumbnail_url,
        is_downloaded=False,
        download_progress=0.0,
        slug=unique_slug,
    )
    
    # Set duration if available
    if video_info.duration_seconds:
        video.duration_seconds = video_info.duration_seconds
    
    db.add(video)
    db.commit()
    db.refresh(video)
    
    logger.info(
        "video.created_from_youtube_metadata",
        video_id=video.id,
        youtube_video_id=video_info.video_id,
        title=video_info.title[:50],
        slug=unique_slug,
    )
    
    return video


async def create_from_youtube(
    db: Session,
    user: User,
    youtube_url: str,
    video_type: str,
    aspect_ratio: str,
    clip_length_preset: str,
    subtitle: bool,
    progress_callback: callable = None,
) -> tuple[VideoSource, ProcessingJob]:
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "videos", str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    # Extract video ID for YouTube-specific fields
    youtube_video_id = youtube_metadata_service.extract_video_id(youtube_url)
    youtube_thumbnail_url = None
    if youtube_video_id:
        youtube_thumbnail_url = youtube_metadata_service.get_thumbnail_url(youtube_video_id)
    
    # Generate unique slug (will be updated with actual title after download)
    base_slug = slug_service.generate_slug(youtube_url)
    existing_slugs = _get_existing_slugs(db)
    unique_slug = slug_service.ensure_unique_slug(base_slug, existing_slugs)

    video = VideoSource(
        user_id=user.id,
        source_type="youtube",
        source_url=youtube_url,
        title=youtube_url,
        status="pending",
        youtube_video_id=youtube_video_id,
        youtube_thumbnail_url=youtube_thumbnail_url,
        is_downloaded=False,
        download_progress=0.0,
        slug=unique_slug,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Download highest quality mp4 via yt_dlp with retry logic.
    if YoutubeDL is None:
        raise RuntimeError("yt_dlp not installed; cannot download YouTube video")
    target_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    
    # Progress hook for yt-dlp
    def progress_hook(d):
        if progress_callback and d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
                speed = d.get('speed', 0)
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "calculating..."
                progress_callback(percent, f"Downloading: {percent:.1f}% ({speed_str})")
        elif progress_callback and d['status'] == 'finished':
            progress_callback(100, "Download complete, processing...")
    
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": target_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "progress_hooks": [progress_hook],
    }

    max_retries = settings.youtube_download_retries
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("youtube.download_attempt", attempt=attempt, max_retries=max_retries, url=youtube_url)
            if progress_callback:
                progress_callback(0, f"Starting download (attempt {attempt}/{max_retries})...")
            
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
                        logger.info("youtube.thumbnail_url_found", thumbnail_url=thumbnail_url)
                ydl.download([youtube_url])
            
            if progress_callback:
                progress_callback(100, "Analyzing video...")
            
            video.file_path = target_path
            video.is_downloaded = True
            video.download_progress = 100.0
            duration = utils.probe_duration(target_path)
            if duration:
                video.duration_seconds = duration
            
            # Update slug with actual title if title was updated
            if video.title and video.title != youtube_url:
                new_base_slug = slug_service.generate_slug(video.title)
                # Re-fetch existing slugs excluding current video's slug
                current_slugs = [s for s in _get_existing_slugs(db) if s != video.slug]
                video.slug = slug_service.ensure_unique_slug(new_base_slug, current_slugs)
            
            # Download YouTube original thumbnail and save locally
            thumb_dir = utils.ensure_dir(Path(settings.media_root) / "thumbnails" / "videos" / str(video.id))
            thumb_path = thumb_dir / "thumb.jpg"
            
            thumbnail_saved = False
            if thumbnail_url:
                # Download YouTube thumbnail
                thumbnail_saved = utils.download_thumbnail(thumbnail_url, str(thumb_path))
                if thumbnail_saved:
                    try:
                        relative = thumb_path.relative_to(Path(settings.media_root))
                        video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                        logger.info("youtube.thumbnail_downloaded", video_id=video.id, url=thumbnail_url)
                    except Exception:
                        video.thumbnail_path = str(thumb_path)
            
            # Fallback: generate from video if download failed
            if not thumbnail_saved:
                thumb_timestamp = (duration or 10) * 0.1
                if utils.render_thumbnail(target_path, str(thumb_path), thumb_timestamp):
                    try:
                        relative = thumb_path.relative_to(Path(settings.media_root))
                        video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    except Exception:
                        video.thumbnail_path = str(thumb_path)
                    logger.info("youtube.thumbnail_generated_fallback", video_id=video.id)
            
            db.commit()
            logger.info("youtube.download_success", video_id=video.id, attempt=attempt)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logger.warning("youtube.download_failed", attempt=attempt, error=str(exc))
            if attempt < max_retries:
                if progress_callback:
                    progress_callback(0, f"Retrying... (attempt {attempt + 1}/{max_retries})")
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

    # Generate unique slug from filename
    title = upload_file.filename or "untitled"
    base_slug = slug_service.generate_slug(title)
    existing_slugs = _get_existing_slugs(db)
    unique_slug = slug_service.ensure_unique_slug(base_slug, existing_slugs)

    video = VideoSource(
        user_id=user.id,
        source_type="upload",
        file_path=file_path,
        title=title,
        status="pending",
        is_downloaded=True,  # Uploaded files are already "downloaded"
        download_progress=100.0,
        slug=unique_slug,
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


async def trigger_video_download(
    db: Session,
    video: VideoSource,
    progress_callback: callable = None,
) -> VideoSource:
    """
    Trigger download of a YouTube video that was created with metadata only.
    
    This function downloads the video file for a VideoSource that was created
    using create_video_from_youtube_url(). It updates download_progress during
    download and sets is_downloaded=True when complete.
    
    Args:
        db: Database session
        video: VideoSource record to download (must have source_url set)
        progress_callback: Optional callback(percent, message) for progress updates
        
    Returns:
        Updated VideoSource with file_path set and is_downloaded=True
        
    Raises:
        RuntimeError: If yt_dlp is not installed or download fails
        ValueError: If video is already downloaded or has no source URL
    """
    # Check if already downloaded
    if video.is_downloaded:
        logger.info("video.already_downloaded", video_id=video.id)
        return video
    
    # Validate source URL exists
    if not video.source_url:
        raise ValueError(f"Video {video.id} has no source URL to download from")
    
    if video.source_type != "youtube":
        raise ValueError(f"Video {video.id} is not a YouTube video")
    
    if YoutubeDL is None:
        raise RuntimeError("yt_dlp not installed; cannot download YouTube video")
    
    # Set up download directory
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "videos", str(video.user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    target_path = os.path.join(user_dir, f"{uuid.uuid4().hex}.mp4")
    youtube_url = video.source_url
    
    # Progress hook for yt-dlp that also updates database
    def progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
                video.download_progress = percent
                db.commit()
                
                if progress_callback:
                    speed = d.get('speed', 0)
                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "calculating..."
                    progress_callback(percent, f"Downloading: {percent:.1f}% ({speed_str})")
        elif d['status'] == 'finished':
            video.download_progress = 100.0
            db.commit()
            if progress_callback:
                progress_callback(100, "Download complete, processing...")
    
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": target_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "progress_hooks": [progress_hook],
    }
    
    max_retries = settings.youtube_download_retries
    last_error = None
    thumbnail_url = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "youtube.download_trigger_attempt",
                video_id=video.id,
                attempt=attempt,
                max_retries=max_retries,
            )
            
            if progress_callback:
                progress_callback(0, f"Starting download (attempt {attempt}/{max_retries})...")
            
            with YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get metadata
                info = ydl.extract_info(youtube_url, download=False)
                if info:
                    # Update title if we got a better one
                    if info.get("title") and video.title == youtube_url:
                        video.title = info.get("title")
                        # Update slug with actual title
                        new_base_slug = slug_service.generate_slug(video.title)
                        current_slugs = [s for s in _get_existing_slugs(db) if s != video.slug]
                        video.slug = slug_service.ensure_unique_slug(new_base_slug, current_slugs)
                    
                    # Update duration if available
                    if info.get("duration"):
                        video.duration_seconds = float(info.get("duration"))
                    
                    # Get thumbnail URL
                    thumbnail_url = info.get("thumbnail")
                    if not thumbnail_url:
                        thumbnails = info.get("thumbnails", [])
                        if thumbnails:
                            best_thumb = max(thumbnails, key=lambda t: t.get("height", 0) or 0)
                            thumbnail_url = best_thumb.get("url")
                
                # Now download
                ydl.download([youtube_url])
            
            # Update video record
            video.file_path = target_path
            video.is_downloaded = True
            video.download_progress = 100.0
            
            # Probe duration from file if not set
            if not video.duration_seconds:
                duration = utils.probe_duration(target_path)
                if duration:
                    video.duration_seconds = duration
            
            # Download/generate thumbnail
            thumb_dir = utils.ensure_dir(
                Path(settings.media_root) / "thumbnails" / "videos" / str(video.id)
            )
            thumb_path = thumb_dir / "thumb.jpg"
            
            thumbnail_saved = False
            if thumbnail_url:
                thumbnail_saved = utils.download_thumbnail(thumbnail_url, str(thumb_path))
                if thumbnail_saved:
                    try:
                        relative = thumb_path.relative_to(Path(settings.media_root))
                        video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                        logger.info("youtube.thumbnail_downloaded", video_id=video.id)
                    except Exception:
                        video.thumbnail_path = str(thumb_path)
            
            # Fallback: generate from video
            if not thumbnail_saved:
                thumb_timestamp = (video.duration_seconds or 10) * 0.1
                if utils.render_thumbnail(target_path, str(thumb_path), thumb_timestamp):
                    try:
                        relative = thumb_path.relative_to(Path(settings.media_root))
                        video.thumbnail_path = f"{settings.media_base_url}/{relative.as_posix()}"
                    except Exception:
                        video.thumbnail_path = str(thumb_path)
            
            db.commit()
            db.refresh(video)
            
            logger.info(
                "youtube.download_trigger_success",
                video_id=video.id,
                attempt=attempt,
                file_path=target_path,
            )
            return video
            
        except Exception as exc:
            last_error = exc
            logger.warning(
                "youtube.download_trigger_failed",
                video_id=video.id,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_retries:
                if progress_callback:
                    progress_callback(0, f"Retrying... (attempt {attempt + 1}/{max_retries})")
                time.sleep(settings.retry_delay_seconds)
            else:
                video.status = "failed"
                video.error_message = f"Download failed after {max_retries} attempts: {str(exc)}"
                db.commit()
    
    if last_error:
        raise last_error
    
    return video
