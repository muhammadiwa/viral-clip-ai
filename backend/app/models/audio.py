from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class AudioConfig(Base, TimestampMixin):
    __tablename__ = "audio_configs"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False)
    bgm_track_id = Column(String)
    bgm_volume = Column(Float, default=0.25)
    original_volume = Column(Float, default=1.0)
    ai_voice_provider = Column(String)
    ai_voice_id = Column(String)
    language = Column(String, default="en")
    mode = Column(String, default="overlay")  # replace|overlay

    clip = relationship("Clip", back_populates="audio_config")
