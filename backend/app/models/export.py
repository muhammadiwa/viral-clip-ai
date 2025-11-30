from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.clip import Clip


class ExportJob(Base, TimestampMixin):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("clips.id"), nullable=False)
    resolution: Mapped[str] = mapped_column(String, default="1080p")
    fps: Mapped[int] = mapped_column(Integer, default=30)
    aspect_ratio: Mapped[str] = mapped_column(String, default="9:16")
    status: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    output_path: Mapped[Optional[str]] = mapped_column(String)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    clip: Mapped["Clip"] = relationship("Clip", back_populates="exports")
