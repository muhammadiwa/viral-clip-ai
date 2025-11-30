from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    credits = Column(Integer, default=100)

    videos = relationship("VideoSource", back_populates="user")
    brand_kit = relationship("BrandKit", back_populates="user", uselist=False)
    subtitle_styles = relationship("SubtitleStyle", back_populates="user")
