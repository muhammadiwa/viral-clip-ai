from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.job import ProcessingJob


class Notification(Base, TimestampMixin):
    """Notification model for user notifications about job processing status."""
    
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="info")  # success|info|warning|error
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    link: Mapped[Optional[str]] = mapped_column(String(500))
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processing_jobs.id"))

    user: Mapped["User"] = relationship("User", back_populates="notifications")
    job: Mapped[Optional["ProcessingJob"]] = relationship("ProcessingJob")
