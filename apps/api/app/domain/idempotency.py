from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IdempotencyRecord(BaseModel):
    """Represents a stored response for a given idempotency key."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    key: str
    method: str
    path: str
    status_code: int
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoredIdempotentResponse(BaseModel):
    status_code: int
    payload: dict[str, Any]

