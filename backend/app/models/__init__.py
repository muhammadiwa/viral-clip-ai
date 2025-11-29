from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    credits = Column(Integer, default=0)

    videos = relationship("VideoSource", back_populates="user")


class AIUsageLog(Base, TimestampMixin):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)


class VideoSource(Base, TimestampMixin):
    __tablename__ = "video_sources"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String, nullable=False)  # youtube | upload
    source_url = Column(String)
    file_path = Column(String)
    title = Column.String
    duration_seconds = Column(Float)
    status = Column(String, default="pending")  # pending|processing|analyzed|ready|failed
    error_message = Column(Text)

    user = relationship("User", back_populates="videos")
    jobs = relationship("ProcessingJob", back_populates="video")


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"))
    job_type = Column(String, nullable=False)
    status = Column(String, default="queued")  # queued|running|completed|failed
    progress = Column(Float, default=0.0)
    payload = Column(JSON)
    result_summary = Column(JSON)

    video = relationship("VideoSource", back_populates="jobs")
