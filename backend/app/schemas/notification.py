"""Notification schemas for API request/response validation."""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


class NotificationBase(BaseModel):
    """Base notification schema with common fields."""
    title: str
    message: str
    type: Literal["success", "info", "warning", "error"] = "info"
    link: Optional[str] = None
    job_id: Optional[int] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a new notification."""
    user_id: int


class NotificationOut(NotificationBase):
    """Schema for notification response."""
    id: int
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationsListResponse(BaseModel):
    """Schema for paginated notifications list response."""
    notifications: list[NotificationOut]
    total: int
    unread_count: int
