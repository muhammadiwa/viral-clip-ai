from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class ClipCreate(BaseModel):
    """Payload used by background workers to persist generated clips."""

    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    title: str | None = None
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    score_components: dict[str, float] | None = Field(
        default=None,
        description="Breakdown of the scoring heuristics applied during discovery",
    )


class ClipStyleStatus(str, Enum):
    """States representing the lifecycle of subtitle styling for a clip."""

    NOT_STYLED = "not_styled"
    STYLE_QUEUED = "style_queued"
    STYLING = "styling"
    STYLED = "styled"
    STYLE_FAILED = "style_failed"


class ClipVoiceStatus(str, Enum):
    """States representing the lifecycle of voice-over synthesis for a clip."""

    NOT_REQUESTED = "not_requested"
    VOICE_QUEUED = "voice_queued"
    SYNTHESIZING = "synthesizing"
    SYNTHESIZED = "synthesized"
    VOICE_FAILED = "voice_failed"


class SubtitleStyleRequest(BaseModel):
    """Requested subtitle styling configuration for a clip."""

    preset: str | None = Field(
        default=None,
        description="Named template or preset identifier to apply",
        examples=["bold-yellow", "brand-kit-a"],
    )
    font_family: str | None = Field(
        default=None,
        description="Override for the subtitle font family",
        examples=["Inter", "Poppins"],
    )
    background_color: str | None = Field(
        default=None,
        description="Hex or rgba color used for subtitle background",
        examples=["#00000080"],
    )
    text_color: str | None = Field(
        default=None,
        description="Primary subtitle text color",
        examples=["#FDE047"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "preset": "bold-yellow",
                    "font_family": "Inter",
                    "background_color": "#00000080",
                    "text_color": "#FDE047",
                }
            ]
        }
    }


class Clip(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    project_id: UUID
    video_id: UUID
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    title: Optional[str] = None
    description: Optional[str] = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    score_components: dict[str, float] | None = None
    style_status: ClipStyleStatus = ClipStyleStatus.NOT_STYLED
    style_preset: Optional[str] = None
    style_settings: dict[str, object] | None = None
    last_styled_at: datetime | None = None
    style_error: Optional[str] = None
    voice_status: ClipVoiceStatus = ClipVoiceStatus.NOT_REQUESTED
    voice_language: Optional[str] = None
    voice_name: Optional[str] = None
    voice_settings: dict[str, object] | None = None
    last_voiced_at: datetime | None = None
    voice_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ClipResponse(BaseModel):
    data: Clip


class ClipListResponse(BaseModel):
    data: list[Clip]
    count: int
    pagination: PaginationMeta


class ClipGenerationRequest(BaseModel):
    """Optional hints when requesting automated clip generation."""

    max_clips: int = Field(default=5, ge=1, le=20)
    strategy: str | None = Field(
        default=None,
        description="Named discovery strategy such as 'default' or 'highlights'",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "max_clips": 8,
                    "strategy": "highlights",
                }
            ]
        }
    }


class ClipGenerationResponse(BaseModel):
    """Returned when a clip discovery job has been enqueued."""

    job_id: UUID
    video_id: UUID
    requested_clips: int
    strategy: str | None = None


class SubtitleStyleResponse(BaseModel):
    """Returned when subtitle styling has been enqueued for a clip."""

    job_id: UUID
    clip_id: UUID
    style_status: ClipStyleStatus


class ClipVoiceRequest(BaseModel):
    """Requested TTS configuration for dubbing a clip."""

    language_code: str = Field(
        default="en-US",
        description="BCP-47 locale for the synthesized narration",
        examples=["en-US", "id-ID"],
    )
    voice: str | None = Field(
        default=None,
        description="Identifier of the preferred voice preset",
        examples=["alloy", "id-female-soft"],
    )
    speaking_rate: float | None = Field(
        default=None,
        ge=0.5,
        le=2.0,
        description="Optional multiplier applied to the default speaking speed",
    )
    emotion: str | None = Field(
        default=None,
        description="Named expressiveness preset for the synthesizer",
        examples=["excited", "calm"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "language_code": "id-ID",
                    "voice": "id-female-soft",
                    "speaking_rate": 1.05,
                    "emotion": "excited",
                }
            ]
        }
    }


class ClipVoiceResponse(BaseModel):
    """Returned when voice-over synthesis has been enqueued for a clip."""

    job_id: UUID
    clip_id: UUID
    voice_status: ClipVoiceStatus


class ClipUpdateRequest(BaseModel):
    """Mutable clip metadata exposed to editorial workflows."""

    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "AI safety hot take",
                    "description": "Hosts debate alignment timelines.",
                    "start_ms": 123400,
                    "end_ms": 145000,
                }
            ]
        }
    }


