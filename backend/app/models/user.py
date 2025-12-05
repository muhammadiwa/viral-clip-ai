from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import Mapped, relationship

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.user_preference import UserPreference


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    credits = Column(Integer, default=100)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    videos = relationship("VideoSource", back_populates="user")
    brand_kit = relationship("BrandKit", back_populates="user", uselist=False)
    subtitle_styles = relationship("SubtitleStyle", back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")
    preferences: Mapped[Optional["UserPreference"]] = relationship("UserPreference", back_populates="user", uselist=False)
