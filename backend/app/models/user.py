from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime
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
    password_hash = Column(String, nullable=True)  # Nullable for Google OAuth users
    is_active = Column(Boolean, default=True)
    credits = Column(Integer, default=100)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Google OAuth fields
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Account lockout fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    videos = relationship("VideoSource", back_populates="user")
    brand_kit = relationship("BrandKit", back_populates="user", uselist=False)
    subtitle_styles = relationship("SubtitleStyle", back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")
    preferences: Mapped[Optional["UserPreference"]] = relationship("UserPreference", back_populates="user", uselist=False)
    
    def is_locked(self) -> bool:
        """Check if the account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    def get_lockout_remaining_seconds(self) -> Optional[int]:
        """Get remaining lockout time in seconds, or None if not locked."""
        if not self.is_locked():
            return None
        remaining = (self.locked_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
