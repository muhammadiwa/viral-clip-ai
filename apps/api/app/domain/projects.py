from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl

from .pagination import PaginationMeta


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=2048)
    source_url: Optional[HttpUrl] = None
    brand_kit_id: Optional[UUID] = None
    brand_overrides: dict[str, object] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2048)
    source_url: Optional[HttpUrl] = None
    brand_kit_id: Optional[UUID] = None
    brand_overrides: Optional[dict[str, object]] = None


class ProjectExportStatus(str, Enum):
    """Lifecycle states for project level exports."""

    NOT_EXPORTED = "not_exported"
    EXPORT_QUEUED = "export_queued"
    EXPORTING = "exporting"
    EXPORTED = "exported"
    EXPORT_FAILED = "export_failed"


class Project(ProjectBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "draft"
    export_status: ProjectExportStatus = ProjectExportStatus.NOT_EXPORTED
    export_settings: dict[str, object] | None = None
    last_exported_at: datetime | None = None
    export_error: Optional[str] = None
    brand_kit_id: UUID | None = None
    brand_overrides: dict[str, object] | None = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    data: list[Project]
    count: int
    pagination: PaginationMeta


class ProjectResponse(BaseModel):
    data: Project


class ProjectExportRequest(BaseModel):
    """Client-provided configuration when exporting a project."""

    format: str = Field(
        default="mp4",
        min_length=2,
        max_length=16,
        description="Container format for the rendered video",
    )
    resolution: str | None = Field(
        default=None,
        description="Preferred output resolution such as 1080p or 4k",
        examples=["1080p", "9:16-1080p"],
    )
    include_subtitles: bool = Field(
        default=True,
        description="Embed styled subtitles into the exported video",
    )
    include_voice_over: bool = Field(
        default=True,
        description="Blend synthesized voice-over into the master mix",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "format": "mp4",
                    "resolution": "1080p",
                    "include_subtitles": True,
                    "include_voice_over": True,
                }
            ]
        }
    }


class ProjectExportResponse(BaseModel):
    """Returned when a project level export job has been enqueued."""

    job_id: UUID
    project_id: UUID
    export_status: ProjectExportStatus
    format: str
    resolution: str | None = None
    include_subtitles: bool
    include_voice_over: bool
