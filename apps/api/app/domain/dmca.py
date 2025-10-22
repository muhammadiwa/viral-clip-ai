from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field

from .pagination import PaginationMeta


class DmcaTargetType(str, Enum):
    """Enumerates the resource types that can be cited in a DMCA notice."""

    PROJECT = "project"
    VIDEO = "video"
    CLIP = "clip"
    OTHER = "other"


class DmcaNoticeStatus(str, Enum):
    """Tracks the review lifecycle of a DMCA notice."""

    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    CONTENT_REMOVED = "content_removed"
    REJECTED = "rejected"
    RESOLVED = "resolved"


class DmcaNoticeBase(BaseModel):
    reporter_name: str = Field(..., min_length=1, max_length=160)
    reporter_email: EmailStr
    target_type: DmcaTargetType = DmcaTargetType.VIDEO
    target_id: Optional[UUID] = Field(
        default=None,
        description="Identifier of the resource referenced in the takedown request",
    )
    infringing_material_description: str = Field(..., min_length=10, max_length=2000)
    original_material_description: str = Field(..., min_length=10, max_length=2000)
    additional_details: Optional[str] = Field(default=None, max_length=4000)
    signature: str = Field(..., min_length=2, max_length=160)


class DmcaNoticeCreate(DmcaNoticeBase):
    pass


class DmcaNotice(DmcaNoticeBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    status: DmcaNoticeStatus = DmcaNoticeStatus.RECEIVED
    action_taken: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Summary of remediation or counter notice action",
    )
    reviewer_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Internal notes captured during review",
    )
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class DmcaNoticeResponse(BaseModel):
    data: DmcaNotice


class DmcaNoticeListResponse(BaseModel):
    data: list[DmcaNotice]
    count: int
    pagination: PaginationMeta


class DmcaNoticeUpdateRequest(BaseModel):
    status: DmcaNoticeStatus | None = Field(default=None)
    action_taken: Optional[str] = Field(default=None, max_length=2000)
    reviewer_notes: Optional[str] = Field(default=None, max_length=2000)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "under_review",
                    "action_taken": "Disabled public playback pending rights verification",
                    "reviewer_notes": "Awaiting claimant proof of ownership.",
                }
            ]
        }
    }
