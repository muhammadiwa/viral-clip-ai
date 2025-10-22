from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RetellStatus(str, Enum):
    """Lifecycle states for movie retell generation."""

    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class RetellCreateRequest(BaseModel):
    """Client-provided preferences for movie retell synthesis."""

    language: str = Field(
        default="en",
        min_length=2,
        max_length=8,
        description="Language code to narrate the retell in",
        examples=["en", "id"],
    )
    target_duration_minutes: int = Field(
        default=45,
        ge=5,
        le=240,
        description="Desired runtime of the condensed retell",
    )
    narration_style: str = Field(
        default="dynamic",
        min_length=3,
        max_length=64,
        description="Narration tone applied to the generated script",
        examples=["dynamic", "documentary", "dramatic"],
    )
    include_voice_over: bool = Field(
        default=True,
        description="Whether to synthesize accompanying voice-over audio",
    )


class Retell(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    project_id: UUID
    job_id: UUID | None = None
    language: str
    target_duration_minutes: int
    narration_style: str
    include_voice_over: bool
    status: RetellStatus = RetellStatus.QUEUED
    summary: Optional[str] = None
    outline: list[str] | None = None
    status_message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class RetellResponse(BaseModel):
    data: Retell


class RetellUpdateRequest(BaseModel):
    """Payload used by workers to persist generated retell results."""

    summary: str | None = Field(
        default=None,
        description="High-level synopsis generated for the retell",
        max_length=8192,
    )
    outline: list[str] | None = Field(
        default=None,
        description="Ordered list of chapter or beat summaries",
        max_length=100,
    )
    status_message: str | None = Field(
        default=None,
        description="Human readable progress update for in-flight retell jobs",
        max_length=1024,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "A concise retelling of the space opera with focus on character arcs.",
                    "outline": [
                        "Opening crawl establishes the galactic conflict",
                        "Heroes assemble to rescue the captured princess",
                        "Climactic battle ends with destruction of the station",
                    ],
                    "status_message": "Assembling final narration tracks",
                }
            ]
        }
    }
