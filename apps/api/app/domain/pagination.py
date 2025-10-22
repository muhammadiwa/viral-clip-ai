from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Common pagination query parameters."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginationMeta(BaseModel):
    """Metadata describing a paginated response."""

    limit: int
    offset: int
    count: int
    total: int
    has_more: bool
    next_offset: int | None = None
