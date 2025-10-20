"""SQLAlchemy model for projects."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


class ProjectModel(Base):
    """Persisted project metadata scoped to an organization."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    export_status: Mapped[str] = mapped_column(
        String(32), default="not_exported", nullable=False
    )
    export_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    export_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    last_exported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    brand_kit_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_kits.id", ondelete="SET NULL"), nullable=True
    )
    brand_overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )

    videos = relationship(
        "VideoModel", back_populates="project", cascade="all, delete-orphan"
    )

    jobs = relationship("JobModel", back_populates="project")

