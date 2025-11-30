from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.common import TimestampMixin


class BrandKit(Base, TimestampMixin):
    __tablename__ = "brand_kits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, default="Default")
    logo_path = Column(String)
    primary_color = Column(String)
    secondary_color = Column(String)
    default_subtitle_style_id = Column(Integer, ForeignKey("subtitle_styles.id"))
    watermark_position = Column(String, default="bottom-right")

    user = relationship("User", back_populates="brand_kit")
    default_subtitle_style = relationship("SubtitleStyle")
