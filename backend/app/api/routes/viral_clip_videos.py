from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, enforce_daily_job_limit, enforce_credits
from app.models import VideoSource, User, TranscriptSegment, SceneSegment, ProcessingJob
from app.schemas import (
    VideoSourceOut,
    VideoCreateResponse,
    VideoInstantResponse,
    TranscriptSegmentOut,
    SceneSegmentOut,
)
from app.services import video_ingest
from app.services.youtube_metadata import YouTubeMetadataError

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


@router.post("/video/youtube/instant", response_model=VideoInstantResponse)
async def create_video_from_youtube_instant(
    youtube_url: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or get existing video record from YouTube URL by fetching metadata only (instant).
    
    This endpoint implements duplicate prevention:
    1. Extracts video ID from URL
    2. Checks if video with same youtube_video_id + user_id exists
    3. If exists, returns existing video with is_existing=True
    4. If not exists, fetches metadata via oEmbed API and creates new record
    5. Generates a unique slug from the video title
    
    The video can be previewed using YouTube embed player.
    Download will be triggered when user requests clip generation.
    
    Returns:
        VideoInstantResponse with:
        - video: The VideoSource record (existing or newly created)
        - is_existing: True if video already existed, False if newly created
    
    Requirements: 1.1, 1.2, 1.3, 2.1, 2.2
    """
    try:
        result = await video_ingest.create_or_get_video_from_youtube(
            db=db,
            user=current_user,
            youtube_url=youtube_url,
        )
        video, is_new = result
        return {"video": video, "is_existing": not is_new}
    except YouTubeMetadataError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.get("/videos/by-slug/{slug}", response_model=VideoSourceOut)
def get_video_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get video by slug (SEO-friendly URL identifier).
    
    Requirements: 6.4, 6.5
    """
    video = (
        db.query(VideoSource)
        .filter(VideoSource.slug == slug, VideoSource.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/videos/{video_id}", response_model=VideoSourceOut)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get video by ID (legacy endpoint, prefer /videos/by-slug/{slug})."""
    video = (
        db.query(VideoSource)
        .filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


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


@router.post("/videos/{video_id}/trigger-download", response_model=VideoSourceOut)
async def trigger_video_download(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger download for a YouTube video that was created with instant preview.
    
    If the video is already downloaded, returns immediately.
    
    Requirements: 4.2, 4.3
    """
    video = (
        db.query(VideoSource)
        .filter(VideoSource.id == video_id, VideoSource.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # If already downloaded, return immediately (idempotent)
    if video.is_downloaded:
        return video
    
    # Only YouTube videos can be downloaded
    if video.source_type != "youtube":
        raise HTTPException(
            status_code=400,
            detail="Only YouTube videos can be downloaded"
        )
    
    # Update status to downloading
    video.status = "downloading"
    db.commit()
    
    try:
        video = await video_ingest.trigger_video_download(db, video)
        return video
    except Exception as e:
        video.status = "failed"
        video.error_message = f"Download failed: {str(e)}"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download video: {str(e)}"
        )


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
