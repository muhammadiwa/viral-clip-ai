from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class ClipBatch(Base, TimestampMixin):
    __tablename__ = "clip_batches"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"))
    name = Column(String, default="default")
    config_json = Column(JSON, default=dict)
    status = Column(String, default="processing")  # draft|processing|ready|final

    video = relationship("VideoSource", back_populates="clip_batches")
    clips = relationship("Clip", back_populates="batch", cascade="all, delete-orphan")


class Clip(Base, TimestampMixin):
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True)
    clip_batch_id = Column(Integer, ForeignKey("clip_batches.id"), nullable=False)
    start_time_sec = Column(Float, nullable=False)
    end_time_sec = Column(Float, nullable=False)
    duration_sec = Column(Float, nullable=False)
    title = Column(String)
    description = Column(Text)
    viral_score = Column(Float)
    grade_hook = Column(String)
    grade_flow = Column(String)
    grade_value = Column(String)
    grade_trend = Column(String)
    language = Column(String, default="en")
    status = Column(String, default="candidate")  # candidate|edited|exported
    thumbnail_path = Column(String)

    batch = relationship("ClipBatch", back_populates="clips")
    subtitles = relationship("SubtitleSegment", back_populates="clip", cascade="all, delete-orphan")
    audio_config = relationship("AudioConfig", back_populates="clip", uselist=False)
    exports = relationship("ExportJob", back_populates="clip", cascade="all, delete-orphan")
    llm_context = relationship("ClipLLMContext", back_populates="clip", uselist=False)


class ClipLLMContext(Base, TimestampMixin):
    __tablename__ = "clip_llm_contexts"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False)
    prompt = Column(Text)
    response_json = Column(JSON)

    clip = relationship("Clip", back_populates="llm_context")
