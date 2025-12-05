from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.schemas.job import ProcessingJobOut


class ClipBatchCreate(BaseModel):
    video_type: str = "podcast"
    aspect_ratio: str = "9:16"
    clip_length_preset: str = "auto_0_60"
    subtitle_enabled: bool = True
    subtitle_style_id: Optional[int] = None
    processing_timeframe_start: Optional[float] = None
    processing_timeframe_end: Optional[float] = None
    include_specific_moments: Optional[str] = None


class ClipBatchOut(BaseModel):
    id: int
    video_source_id: int
    name: str
    status: str
    config_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClipOut(BaseModel):
    id: int
    clip_batch_id: int
    start_time_sec: float
    end_time_sec: float
    duration_sec: float
    title: Optional[str] = None
    description: Optional[str] = None
    viral_score: Optional[float] = None
    grade_hook: Optional[str] = None
    grade_flow: Optional[str] = None
    grade_value: Optional[str] = None
    grade_trend: Optional[str] = None
    language: Optional[str] = None
    status: str
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None
    aspect_ratio: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClipDetailOut(ClipOut):
    video_source_id: int | None = None
    transcript_preview: Optional[str] = None
    subtitle_language: Optional[str] = None
    viral_breakdown: Optional[dict] = None
    hashtags: Optional[List[str]] = None
    hook_text: Optional[str] = None
    detected_video_type: Optional[str] = None


class ClipListResponse(BaseModel):
    clips: List[ClipOut]


class ClipBatchWithJob(BaseModel):
    batch: ClipBatchOut
    job: ProcessingJobOut
