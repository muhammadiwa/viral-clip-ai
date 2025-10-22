"""SQLAlchemy models backing billing persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class SubscriptionModel(Base):
    """Subscription state for an organization."""

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    minutes_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clip_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retell_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_quota_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    renews_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )


class UsageModel(Base):
    """Aggregated usage counters for quota tracking."""

    __tablename__ = "usage_snapshots"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_usage_org"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, unique=True
    )
    minutes_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clips_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retells_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_gb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    minutes_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clip_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retell_quota: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_quota_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )


class PaymentTransactionModel(Base):
    """Midtrans payment attempts and their lifecycle."""

    __tablename__ = "payment_transactions"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    seats: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_amount: Mapped[Numeric] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_status: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    redirect_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    snap_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fraud_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
