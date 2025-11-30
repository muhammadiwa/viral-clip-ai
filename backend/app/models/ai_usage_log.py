from sqlalchemy import Column, Integer, String, ForeignKey

from app.db.base import Base
from app.models.common import TimestampMixin


class AIUsageLog(Base, TimestampMixin):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
