from datetime import datetime

from sqlalchemy import Column, DateTime


class TimestampMixin:
    """Shared timestamp columns for most tables."""

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
