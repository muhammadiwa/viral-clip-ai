from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from app.models.video import VideoSource


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("video_sources.id"))
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|completed|failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[Optional[str]] = mapped_column(String)  # Current step description
    current_step: Mapped[Optional[str]] = mapped_column(String)  # Current step name
    total_steps: Mapped[Optional[int]] = mapped_column(Integer)  # Total steps in this job
    current_step_num: Mapped[Optional[int]] = mapped_column(Integer)  # Current step number
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    result_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    video: Mapped["VideoSource"] = relationship("VideoSource", back_populates="jobs")
