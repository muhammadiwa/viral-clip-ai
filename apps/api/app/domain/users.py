from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field

from .pagination import PaginationMeta


class UserBase(BaseModel):
    """Shared fields for user representations."""

    email: EmailStr = Field(..., description="Primary email used for login and notifications")
    full_name: Optional[str] = Field(
        default=None,
        max_length=160,
        description="Display name shown in the workspace UI",
    )


class UserCreate(UserBase):
    """Payload accepted when creating a new user."""

    password: str = Field(
        ..., min_length=8, max_length=128, description="Raw password to be hashed"
    )
    role: Optional[str] = Field(
        default="viewer",
        description="Role for team member in current organization"
    )


class User(UserBase):
    """Persisted user profile."""

    id: UUID = Field(default_factory=uuid4)
    owned_org_id: Optional[UUID] = Field(
        default=None,
        description="Organization ID that this user owns (null for team members)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Envelope returned for a single user lookup."""

    data: User


class UserListResponse(BaseModel):
    """Envelope returned when listing multiple users."""

    data: list[User]
    count: int
    pagination: PaginationMeta
