from __future__ import annotations

from datetime import datetime
from enum import Enum
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field


class PlanTier(str, Enum):
    """Supported subscription plan tiers."""

    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


class SubscriptionStatus(str, Enum):
    """Lifecycle state of an organization's subscription."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class Subscription(BaseModel):
    """Represents the billing relationship for an organization."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    plan: PlanTier = PlanTier.FREE
    status: SubscriptionStatus = SubscriptionStatus.TRIALING
    seats: int = Field(default=1, ge=1)
    minutes_quota: int = Field(default=0, ge=0)
    clip_quota: int = Field(default=0, ge=0)
    retell_quota: int = Field(default=0, ge=0)
    storage_quota_gb: float = Field(default=0, ge=0)
    renews_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    data: Subscription


class SubscriptionUpdateRequest(BaseModel):
    plan: PlanTier | None = Field(default=None, description="Target plan tier")
    status: SubscriptionStatus | None = Field(
        default=None, description="Override subscription lifecycle status"
    )
    seats: int | None = Field(default=None, ge=1)
    minutes_quota: int | None = Field(default=None, ge=0)
    clip_quota: int | None = Field(default=None, ge=0)
    retell_quota: int | None = Field(default=None, ge=0)
    storage_quota_gb: float | None = Field(default=None, ge=0)
    renews_at: datetime | None = None
    canceled_at: datetime | None = None


class UsageSnapshot(BaseModel):
    """Aggregated usage metrics for an organization."""

    minutes_processed: int = 0
    minutes_quota: Optional[int] = None
    clips_generated: int = 0
    clip_quota: Optional[int] = None
    retells_created: int = 0
    retell_quota: Optional[int] = None
    storage_gb: float = 0
    storage_quota_gb: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UsageResponse(BaseModel):
    data: UsageSnapshot


class UsageIncrementRequest(BaseModel):
    """Incremental usage reported by workers or the API layer."""

    minutes_processed: int = Field(default=0, ge=0)
    clips_generated: int = Field(default=0, ge=0)
    retells_created: int = Field(default=0, ge=0)
    storage_gb: float = Field(default=0, ge=0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "minutes_processed": 30,
                    "clips_generated": 4,
                    "retells_created": 1,
                    "storage_gb": 1.2,
                }
            ]
        }
    }


class PaymentStatus(str, Enum):
    """Normalized states for Midtrans payment transactions."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"

    @property
    def is_success(self) -> bool:  # pragma: no cover - simple enum helper
        return self is PaymentStatus.SUCCESS

    @property
    def is_terminal(self) -> bool:  # pragma: no cover - simple enum helper
        return self in {
            PaymentStatus.SUCCESS,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELED,
            PaymentStatus.EXPIRED,
            PaymentStatus.REFUNDED,
            PaymentStatus.CHARGEBACK,
        }


class PaymentTransaction(BaseModel):
    """Represents a Midtrans payment attempt for a subscription."""

    order_id: str
    org_id: UUID
    plan: PlanTier
    seats: int = Field(ge=1)
    gross_amount: Decimal = Field(ge=0)
    status: PaymentStatus = PaymentStatus.PENDING
    raw_status: str = "pending"
    payment_type: str | None = None
    transaction_time: datetime | None = None
    transaction_id: str | None = None
    redirect_url: AnyHttpUrl | None = None
    snap_token: str | None = None
    customer_email: EmailStr
    customer_name: str
    customer_phone: str | None = None
    fraud_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class PaymentTransactionResponse(BaseModel):
    data: PaymentTransaction
    client_key: str


class PaymentListResponse(BaseModel):
    data: list[PaymentTransaction]
    client_key: str


class PaymentRequest(BaseModel):
    plan: PlanTier
    seats: int = Field(default=1, ge=1)
    customer_name: str
    customer_email: EmailStr
    customer_phone: str | None = None
    success_redirect_url: AnyHttpUrl
    failure_redirect_url: AnyHttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentNotificationRequest(BaseModel):
    order_id: str
    status_code: str
    transaction_status: str
    gross_amount: str
    signature_key: str
    payment_type: str | None = None
    transaction_time: datetime | None = None
    transaction_id: str | None = None
    fraud_status: str | None = None
