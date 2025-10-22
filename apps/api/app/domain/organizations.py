from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class OrganizationBase(BaseModel):
    """Shared fields for organization payloads."""

    name: str = Field(..., min_length=3, max_length=160)
    slug: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]+[a-z0-9]$",
        description="URL-friendly slug used in workspaces and invites",
    )


class OrganizationCreate(OrganizationBase):
    """Payload used when creating an organization."""

    pass


class Organization(OrganizationBase):
    """Persisted organization metadata."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class OrganizationResponse(BaseModel):
    """Envelope returned when retrieving a single organization."""

    data: Organization


class OrganizationListResponse(BaseModel):
    """Envelope returned when listing organizations."""

    data: list[Organization]
    count: int
    pagination: PaginationMeta


class MembershipRole(str, Enum):
    """Roles supported by the Viral Clip AI workspace."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class MembershipStatus(str, Enum):
    """Lifecycle states for organization memberships."""

    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class Membership(BaseModel):
    """Link between a user and an organization with role metadata."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    user_id: UUID
    role: MembershipRole = MembershipRole.VIEWER
    status: MembershipStatus = MembershipStatus.INVITED
    invited_by_user_id: Optional[UUID] = None
    invited_at: datetime = Field(default_factory=datetime.utcnow)
    joined_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class MembershipCreateRequest(BaseModel):
    """Payload accepted when inviting or adding a member."""

    user_id: UUID
    role: MembershipRole = Field(default=MembershipRole.VIEWER)
    status: MembershipStatus = Field(default=MembershipStatus.INVITED)
    invited_by_user_id: Optional[UUID] = Field(default=None)


class MembershipUpdateRequest(BaseModel):
    """Payload accepted when updating membership details."""

    role: Optional[MembershipRole] = None
    status: Optional[MembershipStatus] = None
    joined_at: Optional[datetime] = Field(default=None)


class MembershipResponse(BaseModel):
    """Envelope returned for a single membership."""

    data: Membership


class MembershipListResponse(BaseModel):
    """Envelope returned when listing organization members."""

    data: list[Membership]
    count: int
    pagination: PaginationMeta


class OrganizationCreateRequest(OrganizationBase):
    """Request body when creating a new organization."""

    owner_user_id: Optional[UUID] = Field(
        default=None,
        description="Optional user ID to assign the owner membership",
    )


class OrganizationCreateResponse(BaseModel):
    """Response payload when creating a new organization."""

    data: Organization
    owner_membership: Optional[Membership] = None
