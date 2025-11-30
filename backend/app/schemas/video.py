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
    duration_seconds: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoCreateResponse(BaseModel):
    video: VideoSourceOut
    job: ProcessingJobOut


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
