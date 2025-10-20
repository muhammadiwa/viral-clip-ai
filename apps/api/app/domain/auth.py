"""Schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from .users import User


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
