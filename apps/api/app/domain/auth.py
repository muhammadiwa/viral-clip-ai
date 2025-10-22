"""Schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from .users import User
from .organizations import Organization, Membership


class TokenRequest(BaseModel):
    """Payload for requesting an access token."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="User password for verification"
    )


class TokenResponse(BaseModel):
    """Response returned when issuing a token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class RegisterRequest(BaseModel):
    """Payload for user registration with auto organization creation."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="User password"
    )
    full_name: str = Field(
        ..., min_length=2, max_length=160, description="User full name"
    )
    organization_name: str = Field(
        ..., min_length=3, max_length=160, description="Organization/workspace name"
    )


class RegisterResponse(BaseModel):
    """Response returned when registering a new user."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User
    organization: Organization
    membership: Membership
