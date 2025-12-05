from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class VideoSource(Base, TimestampMixin):
    __tablename__ = "video_sources"
    __table_args__ = (
        UniqueConstraint('youtube_video_id', 'user_id', name='uq_youtube_video_user'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String, nullable=False)  # youtube | upload
    source_url = Column(String)
    file_path = Column(String)
    thumbnail_path = Column(String)  # URL to video thumbnail
    title = Column(String)
    duration_seconds = Column(Float)
    status = Column(String, default="pending")  # pending|processing|analyzed|ready|failed
    error_message = Column(Text)
    
    # Instant YouTube Preview fields
    youtube_video_id = Column(String(50), nullable=True)  # Extracted YouTube video ID
    youtube_thumbnail_url = Column(String(500), nullable=True)  # Direct YouTube thumbnail URL
    is_downloaded = Column(Boolean, default=False, nullable=False)  # Whether video file is downloaded
    download_progress = Column(Float, default=0.0, nullable=False)  # Download progress (0-100)
    slug = Column(String(150), unique=True, nullable=False, index=True)  # URL-friendly identifier

    user = relationship("User", back_populates="videos")
    jobs = relationship("ProcessingJob", back_populates="video")
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="video", cascade="all, delete-orphan"
    )
    scene_segments = relationship(
        "SceneSegment", back_populates="video", cascade="all, delete-orphan"
    )
    clip_batches = relationship("ClipBatch", back_populates="video")


class TranscriptSegment(Base, TimestampMixin):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"))
    start_time_sec = Column(Float, nullable=False)
    end_time_sec = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    speaker = Column(String)
    language = Column(String, default="en")
    words_json = Column(JSON)  # Word-level timestamps: [{"word": "hello", "start": 0.0, "end": 0.5}, ...]

    video = relationship("VideoSource", back_populates="transcript_segments")


class SceneSegment(Base, TimestampMixin):
    __tablename__ = "scene_segments"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"))
    start_time_sec = Column(Float, nullable=False)
    end_time_sec = Column(Float, nullable=False)
    score_energy = Column(Float)
    score_change = Column(Float)

    video = relationship("VideoSource", back_populates="scene_segments")
