"""Pydantic models for QA run reporting, findings, and review."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class QAFindingStatus(str, Enum):
    """Workflow state for individual QA findings."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"
    RESOLVED = "resolved"


class QAReviewStatus(str, Enum):
    """Creative approval status for a QA regression run."""

    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"


class QAFindingBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=64)
    case_name: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=2048)
    reference_urls: list[str] = Field(default_factory=list, max_items=8)
    reference_artifact_ids: list[UUID] = Field(default_factory=list, max_items=16)
    overlay_url: str | None = Field(default=None, max_length=2048)
    overlay_metadata: dict[str, Any] = Field(default_factory=dict)
    due_date: datetime | None = Field(default=None)


class QAFindingCreate(QAFindingBase):
    status: QAFindingStatus = QAFindingStatus.OPEN
    notes: str | None = Field(default=None, max_length=4096)
    assignee_id: UUID | None = None
    assignee_name: str | None = Field(default=None, max_length=120)
    assigned_at: datetime | None = None


class QAFindingUpdate(BaseModel):
    status: QAFindingStatus | None = None
    notes: Optional[str] = Field(default=None, max_length=4096)
    reference_urls: Optional[list[str]] = Field(default=None, max_items=8)
    reference_artifact_ids: Optional[list[UUID]] = Field(
        default=None, max_items=16
    )
    overlay_url: Optional[str] = Field(default=None, max_length=2048)
    overlay_metadata: Optional[dict[str, Any]] = None
    assignee_id: Optional[UUID | None] = None
    assignee_name: Optional[str | None] = Field(default=None, max_length=120)
    assigned_at: Optional[datetime | None] = None
    due_date: Optional[datetime | None] = None


class QAFinding(QAFindingBase):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    status: QAFindingStatus = QAFindingStatus.OPEN
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    assignee_id: UUID | None = None
    assignee_name: str | None = None
    assigned_at: datetime | None = None

    class Config:
        from_attributes = True


class QAReviewBase(BaseModel):
    status: QAReviewStatus
    notes: str | None = Field(default=None, max_length=4096)
    reference_artifact_ids: list[UUID] = Field(default_factory=list, max_items=16)


class QAReviewCreate(QAReviewBase):
    reviewer_id: UUID | None = None


class QAReviewUpdate(BaseModel):
    status: QAReviewStatus | None = None
    notes: str | None = Field(default=None, max_length=4096)
    reference_artifact_ids: list[UUID] | None = Field(default=None, max_items=16)


class QAReview(QAReviewBase):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    reviewer_id: UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class QARunBase(BaseModel):
    dataset_name: str = Field(..., min_length=1, max_length=120)
    dataset_version: str | None = Field(default=None, min_length=1, max_length=40)
    clip_cases: int = Field(ge=0)
    subtitle_cases: int = Field(ge=0)
    mix_cases: int = Field(ge=0)
    watermark_cases: int = Field(ge=0)
    clip_failures: int = Field(ge=0)
    subtitle_failures: int = Field(ge=0)
    mix_failures: int = Field(ge=0)
    watermark_failures: int = Field(ge=0)
    failure_details: list[str] = Field(default_factory=list)
    clip_pass_rate: float = Field(ge=0.0, le=1.0)
    subtitle_pass_rate: float = Field(ge=0.0, le=1.0)
    mix_pass_rate: float = Field(ge=0.0, le=1.0)
    watermark_pass_rate: float = Field(ge=0.0, le=1.0)
    failure_artifact_urls: list[str] = Field(default_factory=list, max_items=16)
    failure_artifact_ids: list[UUID] = Field(default_factory=list, max_items=64)
    locale_coverage: dict[str, int] = Field(default_factory=dict)
    genre_coverage: dict[str, int] = Field(default_factory=dict)
    frame_diff_failures: int = Field(default=0, ge=0)


class QARunCreate(QARunBase):
    findings: list[QAFindingCreate] = Field(default_factory=list)


class QARun(QARunBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    latest_review: QAReview | None = None

    class Config:
        from_attributes = True


class QARunDetail(QARun):
    findings: list[QAFinding] = Field(default_factory=list)
    reviews: list[QAReview] = Field(default_factory=list)


class QARunResponse(BaseModel):
    data: QARunDetail


class QARunListResponse(BaseModel):
    data: list[QARun]
    count: int
    pagination: PaginationMeta


class QAFindingResponse(BaseModel):
    data: QAFinding


class QAFindingListResponse(BaseModel):
    data: list[QAFinding]
    count: int


class QAReviewResponse(BaseModel):
    data: QAReview


class QAReviewListResponse(BaseModel):
    data: list[QAReview]
    count: int
