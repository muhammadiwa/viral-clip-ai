from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class TranscriptStatus(str, Enum):
    """Lifecycle states for automated transcription."""

    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


class AlignmentStatus(str, Enum):
    """Lifecycle states for word-level alignment."""

    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    ALIGNING = "aligning"
    ALIGNED = "aligned"
    FAILED = "failed"


class TranscriptWord(BaseModel):
    """Word-level timing information for a transcript segment."""

    word: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class TranscriptSegment(BaseModel):
    """Segment of transcribed audio with optional word timings."""

    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    words: list[TranscriptWord] | None = None


class TranscriptRequest(BaseModel):
    language_code: str | None = Field(
        default=None,
        description="Optional BCP-47 locale hint for transcription engines",
        examples=["en-US", "id-ID"],
    )
    prompt: str | None = Field(
        default=None,
        description="Optional guiding prompt passed to the ASR model",
        examples=["Podcast hosts discuss AI safety"],
    )


class TranscriptCreate(TranscriptRequest):
    project_id: UUID
    video_id: UUID


class Transcript(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    project_id: UUID
    video_id: UUID
    language_code: str | None = None
    prompt: str | None = None
    status: TranscriptStatus = TranscriptStatus.QUEUED
    alignment_status: AlignmentStatus = AlignmentStatus.NOT_REQUESTED
    segments: list[TranscriptSegment] = Field(default_factory=list)
    aligned_segments: list[TranscriptSegment] = Field(default_factory=list)
    transcription_error: Optional[str] = None
    alignment_error: Optional[str] = None
    last_transcribed_at: datetime | None = None
    last_aligned_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class TranscriptResponse(BaseModel):
    data: Transcript


class TranscriptListResponse(BaseModel):
    data: list[Transcript]
    count: int
    pagination: PaginationMeta


class TranscriptCreationResponse(BaseModel):
    transcript: Transcript
    job_id: UUID


class TranscriptAlignmentResponse(BaseModel):
    transcript: Transcript
    job_id: UUID


class TranscriptUpdateRequest(BaseModel):
    status: TranscriptStatus | None = None
    alignment_status: AlignmentStatus | None = None
    segments: list[TranscriptSegment] | None = None
    aligned_segments: list[TranscriptSegment] | None = None
    transcription_error: str | None = None
    alignment_error: str | None = None

