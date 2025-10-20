from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class JobStatus(str, Enum):
    """Lifecycle states for long running processing jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Pipeline step associated with a job instance."""

    INGEST = "ingest"
    TRANSCODE = "transcode"
    TRANSCRIPTION = "transcription"
    ALIGNMENT = "alignment"
    CLIP_DISCOVERY = "clip_discovery"
    SUBTITLE_RENDER = "subtitle_render"
    TTS_RENDER = "tts_render"
    PROJECT_EXPORT = "project_export"
    MOVIE_RETELL = "movie_retell"


class JobCreate(BaseModel):
    project_id: UUID
    video_id: Optional[UUID] = None
    clip_id: Optional[UUID] = None
    retell_id: Optional[UUID] = None
    transcript_id: Optional[UUID] = None
    job_type: JobType


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    project_id: UUID
    video_id: Optional[UUID] = None
    clip_id: Optional[UUID] = None
    retell_id: Optional[UUID] = None
    transcript_id: Optional[UUID] = None
    job_type: JobType
    status: JobStatus = JobStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    data: Job


class JobListResponse(BaseModel):
    data: list[Job]
    count: int
    pagination: PaginationMeta


class JobUpdateRequest(BaseModel):
    status: JobStatus
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    message: str | None = None


class JobControlRequest(BaseModel):
    message: str | None = None

