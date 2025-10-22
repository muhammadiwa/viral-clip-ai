"""SQLAlchemy model storing QA regression run summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base
from ..domain.qa import QAFindingStatus, QAReviewStatus


class QARunModel(Base):
    """Persists aggregated QA run metadata for creative review."""

    __tablename__ = "qa_runs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False
    )
    dataset_name: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    clip_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtitle_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mix_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    watermark_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clip_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtitle_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mix_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    watermark_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_details: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    clip_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    subtitle_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    mix_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    watermark_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    failure_artifact_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_artifact_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    locale_coverage: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    genre_coverage: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    frame_diff_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    findings = relationship(
        "QAFindingModel", back_populates="run", cascade="all, delete-orphan"
    )
    reviews = relationship(
        "QAReviewModel", back_populates="run", cascade="all, delete-orphan"
    )


class QAFindingModel(Base):
    """Stores structured QA failures for creative review workflows."""

    __tablename__ = "qa_run_findings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("qa_runs.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    case_name: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(2048), nullable=False)
    reference_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reference_artifact_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    overlay_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    overlay_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    status: Mapped[QAFindingStatus] = mapped_column(
        SAEnum(QAFindingStatus), nullable=False, default=QAFindingStatus.OPEN
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    assignee_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )

    run = relationship("QARunModel", back_populates="findings")


class QAReviewModel(Base):
    """Creative approval trail for QA runs."""

    __tablename__ = "qa_run_reviews"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("qa_runs.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[QAReviewStatus] = mapped_column(
        SAEnum(QAReviewStatus), nullable=False, default=QAReviewStatus.PENDING
    )
    notes: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    reference_artifact_ids: Mapped[list[UUID]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )

    run = relationship("QARunModel", back_populates="reviews")
