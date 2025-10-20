"""Domain models describing API rate limiting state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RateLimitStatus(BaseModel):
    """Represents the outcome of a rate limit check."""

    allowed: bool = Field(
        description="Whether the request is permitted under the configured quota",
    )
    limit: int = Field(
        description="Maximum number of requests allowed within the window",
        ge=0,
    )
    remaining: int = Field(
        description="Number of requests still available before hitting the limit",
        ge=0,
    )
    retry_after_seconds: int = Field(
        description="Number of seconds until the quota resets if the request was blocked",
        ge=0,
    )


class RateLimitExceededPayload(BaseModel):
    """Structured error payload returned when a limit is exceeded."""

    message: str = Field(default="Rate limit exceeded")
    limit: int = Field(description="The enforced request cap for the evaluated window", ge=0)
    retry_after: int = Field(
        description="Seconds until clients should retry the blocked action",
        ge=0,
    )
