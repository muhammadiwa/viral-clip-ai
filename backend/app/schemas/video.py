from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.job import ProcessingJobOut


class VideoSourceOut(BaseModel):
    id: int
    title: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Instant YouTube Preview fields
    youtube_video_id: Optional[str] = None
    youtube_thumbnail_url: Optional[str] = None
    is_downloaded: bool = False
    download_progress: float = 0.0
    slug: Optional[str] = None  # Made optional for backward compatibility with legacy data

    model_config = ConfigDict(from_attributes=True)


class VideoCreateResponse(BaseModel):
    video: VideoSourceOut
    job: ProcessingJobOut


class VideoInstantResponse(BaseModel):
    """Response for instant YouTube metadata fetch (no job created).
    
    Attributes:
        video: The VideoSource record (existing or newly created)
        is_existing: True if video already existed for this user, False if newly created
        
    Requirements: 1.3
    """
    video: VideoSourceOut
    is_existing: bool = False


class TranscriptSegmentOut(BaseModel):
    id: int
    start_time_sec: float
    end_time_sec: float
    text: str
    speaker: Optional[str] = None
    language: str

    model_config = ConfigDict(from_attributes=True)


class SceneSegmentOut(BaseModel):
    id: int
    start_time_sec: float
    end_time_sec: float
    score_energy: Optional[float] = None
    score_change: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
