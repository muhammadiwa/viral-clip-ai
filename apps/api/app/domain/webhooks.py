from __future__ import annotations

import secrets
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, Field

from .pagination import PaginationMeta


class WebhookEventType(str, Enum):
    """Enumerates events that can trigger outbound webhooks."""

    JOB_UPDATED = "job.updated"
    VIDEO_STATUS_CHANGED = "video.status_changed"
    CLIP_STATUS_CHANGED = "clip.status_changed"
    PROJECT_EXPORTED = "project.exported"
    RETELL_UPDATED = "retell.updated"
    CLIP_STYLED = "clip.styled"
    CLIP_TTS_COMPLETED = "clip.tts_completed"
    QA_REVIEW_UPDATED = "qa.review.updated"
    QA_FINDING_UPDATED = "qa.finding.updated"
    QA_ASSIGNMENT_UPDATED = "qa.assignment.updated"


class WebhookEndpointBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    url: AnyHttpUrl
    events: list[WebhookEventType] = Field(..., min_length=1)
    is_active: bool = True


class WebhookEndpointCreate(WebhookEndpointBase):
    secret: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="Optional custom signing secret. A random value is generated when omitted.",
    )


class WebhookEndpoint(WebhookEndpointBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    secret: str = Field(default_factory=lambda: secrets.token_hex(16))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class WebhookEndpointResponse(BaseModel):
    data: WebhookEndpoint


class WebhookEndpointListResponse(BaseModel):
    data: list[WebhookEndpoint]
    count: int
    pagination: PaginationMeta


class WebhookEndpointUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    url: Optional[AnyHttpUrl] = None
    events: Optional[list[WebhookEventType]] = Field(default=None, min_length=1)
    is_active: Optional[bool] = None
    secret: Optional[str] = Field(default=None, min_length=16, max_length=128)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Clip pipeline webhooks",
                    "events": ["job.updated", "project.exported"],
                }
            ]
        }
    }


class WebhookDeliveryStatus(str, Enum):
    """Represents the status of webhook delivery attempts."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WebhookDelivery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    endpoint_id: UUID
    event_type: WebhookEventType
    payload: dict[str, Any]
    status: WebhookDeliveryStatus = WebhookDeliveryStatus.PENDING
    response_code: Optional[int] = Field(default=None, ge=100, le=599)
    error_message: Optional[str] = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: datetime | None = None

    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    data: WebhookDelivery


class WebhookDeliveryListResponse(BaseModel):
    data: list[WebhookDelivery]
    count: int
    pagination: PaginationMeta


class WebhookDeliveryCreate(BaseModel):
    endpoint_id: UUID
    event_type: WebhookEventType
    payload: dict[str, Any]


class WebhookDeliveryUpdate(BaseModel):
    status: WebhookDeliveryStatus
    response_code: Optional[int] = Field(default=None, ge=100, le=599)
    error_message: Optional[str] = Field(default=None, max_length=4000)

