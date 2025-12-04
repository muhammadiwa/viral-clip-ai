from sqlalchemy import Column, Integer, Float, String, Boolean, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class SubtitleSegment(Base, TimestampMixin):
    __tablename__ = "subtitle_segments"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False)
    start_time_sec = Column(Float, nullable=False)
    end_time_sec = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    language = Column(String, default="en")
    words_json = Column(JSON)  # Word-level timestamps: [{"word": "hello", "start": 0.0, "end": 0.5}, ...]

    clip = relationship("Clip", back_populates="subtitles")


class SubtitleStyle(Base, TimestampMixin):
    __tablename__ = "subtitle_styles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    style_json = Column(JSON, nullable=False)
    is_default_global = Column(Boolean, default=False)

    user = relationship("User", back_populates="subtitle_styles")
