from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(Base, TimestampMixin):
    """User preference model for storing theme and language settings."""
    
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    theme: Mapped[str] = mapped_column(String(20), default="light")  # light|dark|system
    language: Mapped[str] = mapped_column(String(10), default="en")

    user: Mapped["User"] = relationship("User", back_populates="preferences")
