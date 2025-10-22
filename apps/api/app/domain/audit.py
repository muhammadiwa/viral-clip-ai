from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .organizations import MembershipRole
from .pagination import PaginationMeta


class AuditLogCreate(BaseModel):
    """Payload describing an auditable event triggered by a user."""

    action: str = Field(..., min_length=1, max_length=160)
    target_type: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Category of resource acted upon (project, job, video, etc.)",
    )
    target_id: Optional[UUID] = Field(
        default=None,
        description="Identifier of the resource affected by the action",
    )
    target_display_name: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Human readable resource label captured for context",
    )
    message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional free-form explanation attached to the event",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Structured payload for downstream analytics",
    )


class AuditLog(BaseModel):
    """Persisted audit event enriched with actor metadata."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    actor_id: UUID
    actor_email: str | None = None
    actor_role: MembershipRole | None = None
    action: str
    target_type: str | None = None
    target_id: UUID | None = None
    target_display_name: str | None = None
    message: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    data: AuditLog


class AuditLogListResponse(BaseModel):
    data: list[AuditLog]
    count: int
    pagination: PaginationMeta
