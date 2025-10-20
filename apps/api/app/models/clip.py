"""SQLAlchemy model for generated clips."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class ClipModel(Base):
    """Persisted representation of an automatically generated clip."""

    __tablename__ = "clips"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False
    )
    video_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_components: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    style_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_styled"
    )
    style_preset: Mapped[str | None] = mapped_column(String(120), nullable=True)
    style_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_styled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    style_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    voice_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_requested"
    )
    voice_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    voice_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_voiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    voice_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
