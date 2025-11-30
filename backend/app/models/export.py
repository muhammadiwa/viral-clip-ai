from sqlalchemy import Column, Integer, String, ForeignKey, Text, Float
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class ExportJob(Base, TimestampMixin):
    __tablename__ = "exports"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False)
    resolution = Column(String, default="1080p")
    fps = Column(Integer, default=30)
    aspect_ratio = Column(String, default="9:16")
    status = Column(String, default="queued")
    progress = Column(Float, default=0.0)
    output_path = Column(String)
    error_message = Column(Text)

    clip = relationship("Clip", back_populates="exports")
