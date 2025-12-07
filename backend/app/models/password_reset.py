"""
Password Reset Token model for handling password reset requests.

Requirements: 8.2
- WHEN a user submits a valid email for password reset THEN the Auth_System 
  SHALL send a password reset email with a secure time-limited token
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped

from app.db.base import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PasswordResetToken(Base, TimestampMixin):
    """
    Model for storing password reset tokens.
    
    Each token is associated with a user and has an expiration time.
    Tokens can only be used once.
    """
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)  # Hashed token
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    
    # Relationship to user
    user: Mapped["User"] = relationship("User", backref="password_reset_tokens")
    
    def is_valid(self) -> bool:
        """Check if the token is still valid (not expired and not used)."""
        if self.used:
            return False
        return datetime.utcnow() < self.expires_at
    
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.utcnow() >= self.expires_at
    
    def mark_as_used(self) -> None:
        """Mark the token as used."""
        self.used = True
