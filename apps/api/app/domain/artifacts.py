from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class ArtifactKind(str, Enum):
    """Categorization for generated media artifacts."""

    VIDEO_PREVIEW = "video_preview"
    VIDEO_EXPORT = "video_export"
    CLIP_PREVIEW = "clip_preview"
    CLIP_SUBTITLE = "clip_subtitle"
    CLIP_AUDIO = "clip_audio"
    CLIP_AUDIO_MIX = "clip_audio_mix"
    RETELL_SCRIPT = "retell_script"
    RETELL_AUDIO = "retell_audio"


class ArtifactBase(BaseModel):
    kind: ArtifactKind
    uri: str = Field(
        description="Storage location or CDN URL for the generated artifact",
    )
    content_type: Optional[str] = Field(
        default=None,
        description="MIME type describing the stored artifact",
    )
    size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Approximate size of the artifact in bytes for quota tracking",
    )


class ArtifactCreate(ArtifactBase):
    project_id: UUID
    video_id: Optional[UUID] = None
    clip_id: Optional[UUID] = None
    retell_id: Optional[UUID] = None


class ArtifactRegisterRequest(ArtifactBase):
    """Payload workers use when registering new artifacts for a resource."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "kind": "video_export",
                    "uri": "s3://viral-clip-ai/org/project/export/final.mp4",
                    "content_type": "video/mp4",
                    "size_bytes": 245678901,
                }
            ]
        }
    }


class Artifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    project_id: UUID
    video_id: Optional[UUID] = None
    clip_id: Optional[UUID] = None
    retell_id: Optional[UUID] = None
    kind: ArtifactKind
    uri: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ArtifactResponse(BaseModel):
    data: Artifact


class ArtifactListResponse(BaseModel):
    data: list[Artifact]
    count: int
    pagination: PaginationMeta
