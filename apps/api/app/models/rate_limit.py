"""SQLAlchemy model for rate limit counters."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class RateLimitCounterModel(Base):
    """Tracks request counts per scope/key within a time window."""

    __tablename__ = "rate_limits"
    __table_args__ = (UniqueConstraint("scope", "identity", name="uq_rate_scope_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    identity: Mapped[str] = mapped_column(String(255), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
