"""Utilities for deriving billing plan pricing and quotas from configuration."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict

from ..domain.billing import PlanTier, Subscription, SubscriptionStatus
from .config import get_settings


def _plan_price_map() -> Dict[PlanTier, int]:
    settings = get_settings()
    return {
        PlanTier.FREE: settings.plan_price_free_idr,
        PlanTier.PRO: settings.plan_price_pro_idr,
        PlanTier.BUSINESS: settings.plan_price_business_idr,
    }


def _plan_minutes_map() -> Dict[PlanTier, int]:
    settings = get_settings()
    return {
        PlanTier.FREE: settings.plan_minutes_quota_free,
        PlanTier.PRO: settings.plan_minutes_quota_pro,
        PlanTier.BUSINESS: settings.plan_minutes_quota_business,
    }


def _plan_clip_map() -> Dict[PlanTier, int]:
    settings = get_settings()
    return {
        PlanTier.FREE: settings.plan_clip_quota_free,
        PlanTier.PRO: settings.plan_clip_quota_pro,
        PlanTier.BUSINESS: settings.plan_clip_quota_business,
    }


def _plan_retell_map() -> Dict[PlanTier, int]:
    settings = get_settings()
    return {
        PlanTier.FREE: settings.plan_retell_quota_free,
        PlanTier.PRO: settings.plan_retell_quota_pro,
        PlanTier.BUSINESS: settings.plan_retell_quota_business,
    }


def _plan_storage_map() -> Dict[PlanTier, float]:
    settings = get_settings()
    return {
        PlanTier.FREE: settings.plan_storage_quota_gb_free,
        PlanTier.PRO: settings.plan_storage_quota_gb_pro,
        PlanTier.BUSINESS: settings.plan_storage_quota_gb_business,
    }


def calculate_subscription_amount(plan: PlanTier, seats: int) -> int:
    """Return the gross amount (in IDR) for the requested plan and seat count."""

    if seats < 1:
        raise ValueError("Seat count must be at least 1")
    price = _plan_price_map()[plan]
    return price * seats


def get_plan_limits(plan: PlanTier) -> Dict[str, float | int]:
    """Return the quota limits associated with a plan tier."""

    return {
        "minutes_quota": _plan_minutes_map()[plan],
        "clip_quota": _plan_clip_map()[plan],
        "retell_quota": _plan_retell_map()[plan],
        "storage_quota_gb": _plan_storage_map()[plan],
    }


def apply_plan(subscription: Subscription, plan: PlanTier, seats: int) -> Subscription:
    """Apply plan defaults and seat counts to a subscription model."""

    limits = get_plan_limits(plan)
    update = {
        "plan": plan,
        "seats": seats,
        **limits,
    }
    return subscription.model_copy(update=update)


def compute_trial_end(now: datetime | None = None) -> datetime | None:
    """Return the trial expiration timestamp if a trial is configured."""

    settings = get_settings()
    if settings.subscription_trial_days == 0:
        return None
    current = now or datetime.utcnow()
    return current + timedelta(days=settings.subscription_trial_days)


def compute_renewal_at(now: datetime | None = None) -> datetime:
    """Return the next renewal timestamp for an active subscription."""

    settings = get_settings()
    current = now or datetime.utcnow()
    return current + timedelta(days=settings.subscription_cycle_days)


def as_decimal_idr(amount: int) -> Decimal:
    """Convert an integer amount of IDR to a Decimal for downstream usage."""

    return Decimal(amount)


def mark_subscription_active(subscription: Subscription) -> Subscription:
    """Ensure the subscription status reflects an active billing relationship."""

    return subscription.model_copy(update={"status": SubscriptionStatus.ACTIVE})
