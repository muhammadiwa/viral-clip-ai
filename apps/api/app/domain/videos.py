from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl

from .jobs import Job
from .pagination import PaginationMeta


class VideoSourceType(str, Enum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class VideoStatus(str, Enum):
    PENDING_INGEST = "pending_ingest"
    INGEST_QUEUED = "ingest_queued"
    INGESTING = "ingesting"
    READY_FOR_TRANSCODE = "ready_for_transcode"
    TRANSCODE_QUEUED = "transcode_queued"
    TRANSCODING = "transcoding"
    READY_FOR_TRANSCRIPTION = "ready_for_transcription"
    TRANSCRIPTION_QUEUED = "transcription_queued"
    TRANSCRIBING = "transcribing"
    READY_FOR_ALIGNMENT = "ready_for_alignment"
    ALIGNMENT_QUEUED = "alignment_queued"
    ALIGNING = "aligning"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYSIS_QUEUED = "analysis_queued"
    ANALYZING = "analyzing"
    READY_FOR_CLIP_REVIEW = "ready_for_clip_review"
    INGEST_FAILED = "ingest_failed"
    TRANSCODE_FAILED = "transcode_failed"
    TRANSCRIPTION_FAILED = "transcription_failed"
    ALIGNMENT_FAILED = "alignment_failed"
    ANALYSIS_FAILED = "analysis_failed"


class VideoIngestRequest(BaseModel):
    project_id: UUID
    source_type: VideoSourceType = Field(default=VideoSourceType.UPLOAD)
    upload_key: Optional[str] = Field(
        default=None,
        description="Object storage key for uploaded assets",
    )
    source_url: Optional[HttpUrl] = Field(
        default=None,
        description="Public URL for remote sources such as YouTube",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
                    "source_type": "youtube",
                    "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                }
            ]
        }
    }


class Video(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    org_id: UUID
    source_type: VideoSourceType
    upload_key: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    status: VideoStatus = VideoStatus.PENDING_INGEST
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Duration of the source media in milliseconds",
    )
    frame_rate: float | None = Field(
        default=None,
        ge=0,
        description="Average frames per second detected during analysis",
    )
    width: int | None = Field(
        default=None,
        ge=0,
        description="Horizontal resolution of the source media",
    )
    height: int | None = Field(
        default=None,
        ge=0,
        description="Vertical resolution of the source media",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    data: Video


class VideoIngestResponse(BaseModel):
    video: Video
    job: Job
    upload: "VideoUploadCredentials" | None = None


class VideoListResponse(BaseModel):
    data: list[Video]
    count: int
    pagination: PaginationMeta


class VideoUploadCredentials(BaseModel):
    object_key: str
    upload_url: AnyHttpUrl
    expires_in: int
    headers: dict[str, str] = Field(default_factory=dict)

