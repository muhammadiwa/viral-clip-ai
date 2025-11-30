from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True)
    video_source_id = Column(Integer, ForeignKey("video_sources.id"))
    job_type = Column(String, nullable=False)
    status = Column(String, default="queued")  # queued|running|completed|failed
    progress = Column(Float, default=0.0)
    payload = Column(JSON)
    result_summary = Column(JSON)
    error_message = Column(Text)

    video = relationship("VideoSource", back_populates="jobs")
