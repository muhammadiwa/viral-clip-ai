from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import plans
from ..domain.billing import (
    PaymentTransaction,
    PlanTier,
    Subscription,
    SubscriptionStatus,
    SubscriptionUpdateRequest,
    UsageIncrementRequest,
    UsageSnapshot,
)
from ..models.billing import (
    PaymentTransactionModel,
    SubscriptionModel,
    UsageModel,
)


@dataclass
class _UsageState:
    minutes_processed: int = 0
    clips_generated: int = 0
    retells_created: int = 0
    storage_gb: float = 0.0
    updated_at: datetime = datetime.utcnow()


class BillingRepository(Protocol):
    async def get_subscription(self, org_id: UUID) -> Subscription:
        ...

    async def update_subscription(
        self, org_id: UUID, payload: SubscriptionUpdateRequest
    ) -> Subscription:
        ...

    async def get_usage(self, org_id: UUID) -> UsageSnapshot:
        ...

    async def record_usage(
        self, org_id: UUID, payload: UsageIncrementRequest
    ) -> UsageSnapshot:
        ...

    async def save_payment_transaction(
        self, org_id: UUID, transaction: PaymentTransaction
    ) -> PaymentTransaction:
        ...

    async def get_payment_transaction(
        self, org_id: UUID, order_id: str
    ) -> PaymentTransaction | None:
        ...

    async def list_payment_transactions(
        self, org_id: UUID
    ) -> list[PaymentTransaction]:
        ...

    async def get_org_id_for_order(self, order_id: str) -> UUID | None:
        ...

    async def activate_subscription_from_payment(
        self, org_id: UUID, plan: PlanTier, seats: int
    ) -> Subscription:
        ...


class InMemoryBillingRepository(BillingRepository):
    """Stores subscription and usage data in memory for development."""

    def __init__(self) -> None:
        self._subscriptions: dict[UUID, Subscription] = {}
        self._usage: dict[UUID, _UsageState] = defaultdict(_UsageState)
        self._payments: dict[UUID, dict[str, PaymentTransaction]] = defaultdict(dict)
        self._order_to_org: dict[str, UUID] = {}

    async def get_subscription(self, org_id: UUID) -> Subscription:
        subscription = self._subscriptions.get(org_id)
        if subscription:
            return subscription
        subscription = Subscription(org_id=org_id)
        subscription = plans.apply_plan(subscription, PlanTier.FREE, seats=subscription.seats)
        subscription = subscription.model_copy(
            update={
                "renews_at": plans.compute_trial_end(),
                "updated_at": datetime.utcnow(),
            }
        )
        self._subscriptions[org_id] = subscription
        return subscription

    async def update_subscription(
        self, org_id: UUID, payload: SubscriptionUpdateRequest
    ) -> Subscription:
        subscription = await self.get_subscription(org_id)
        update_data = payload.model_dump(exclude_unset=True)
        updated_subscription = subscription.model_copy(update=update_data)
        if "plan" in update_data or "seats" in update_data:
            plan = update_data.get("plan", updated_subscription.plan)
            seats = update_data.get("seats", updated_subscription.seats)
            updated_subscription = plans.apply_plan(updated_subscription, plan, seats)
        updated_subscription.updated_at = datetime.utcnow()
        self._subscriptions[org_id] = updated_subscription
        return updated_subscription

    async def get_usage(self, org_id: UUID) -> UsageSnapshot:
        subscription = await self.get_subscription(org_id)
        usage_state = self._usage[org_id]
        return UsageSnapshot(
            minutes_processed=usage_state.minutes_processed,
            minutes_quota=subscription.minutes_quota,
            clips_generated=usage_state.clips_generated,
            clip_quota=subscription.clip_quota,
            retells_created=usage_state.retells_created,
            retell_quota=subscription.retell_quota,
            storage_gb=usage_state.storage_gb,
            storage_quota_gb=subscription.storage_quota_gb,
            updated_at=usage_state.updated_at,
        )

    async def record_usage(
        self, org_id: UUID, payload: UsageIncrementRequest
    ) -> UsageSnapshot:
        usage_state = self._usage[org_id]
        update_data = payload.model_dump()
        usage_state.minutes_processed += update_data["minutes_processed"]
        usage_state.clips_generated += update_data["clips_generated"]
        usage_state.retells_created += update_data["retells_created"]
        usage_state.storage_gb += update_data["storage_gb"]
        usage_state.updated_at = datetime.utcnow()
        return await self.get_usage(org_id)

    async def save_payment_transaction(
        self, org_id: UUID, transaction: PaymentTransaction
    ) -> PaymentTransaction:
        self._payments[org_id][transaction.order_id] = transaction
        self._order_to_org[transaction.order_id] = org_id
        return transaction

    async def get_payment_transaction(
        self, org_id: UUID, order_id: str
    ) -> PaymentTransaction | None:
        return self._payments[org_id].get(order_id)

    async def list_payment_transactions(
        self, org_id: UUID
    ) -> list[PaymentTransaction]:
        return list(self._payments[org_id].values())

    async def get_org_id_for_order(self, order_id: str) -> UUID | None:
        return self._order_to_org.get(order_id)

    async def activate_subscription_from_payment(
        self, org_id: UUID, plan: PlanTier, seats: int
    ) -> Subscription:
        subscription = await self.get_subscription(org_id)
        subscription = plans.apply_plan(subscription, plan, seats)
        subscription = plans.mark_subscription_active(subscription)
        subscription = subscription.model_copy(
            update={
                "renews_at": plans.compute_renewal_at(),
                "updated_at": datetime.utcnow(),
                "canceled_at": None,
            }
        )
        self._subscriptions[org_id] = subscription
        return subscription


class SqlAlchemyBillingRepository(BillingRepository):
    """Billing repository persisted via SQLAlchemy and Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_subscription_model(
        self, org_id: UUID
    ) -> SubscriptionModel | None:
        result = await self._session.execute(
            select(SubscriptionModel).where(SubscriptionModel.org_id == org_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _model_to_subscription(model: SubscriptionModel) -> Subscription:
        return Subscription(
            id=model.id,
            org_id=model.org_id,
            plan=PlanTier(model.plan),
            status=SubscriptionStatus(model.status),
            seats=model.seats,
            minutes_quota=model.minutes_quota,
            clip_quota=model.clip_quota,
            retell_quota=model.retell_quota,
            storage_quota_gb=model.storage_quota_gb,
            renews_at=model.renews_at,
            canceled_at=model.canceled_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_subscription(self, org_id: UUID) -> Subscription:
        model = await self._get_subscription_model(org_id)
        if model:
            return self._model_to_subscription(model)

        now = datetime.utcnow()
        subscription = Subscription(org_id=org_id)
        subscription = plans.apply_plan(
            subscription, PlanTier.FREE, seats=subscription.seats
        )
        subscription = subscription.model_copy(
            update={
                "status": SubscriptionStatus.TRIALING,
                "renews_at": plans.compute_trial_end(now),
                "created_at": now,
                "updated_at": now,
            }
        )
        model = SubscriptionModel(
            id=subscription.id,
            org_id=subscription.org_id,
            plan=subscription.plan.value,
            status=subscription.status.value,
            seats=subscription.seats,
            minutes_quota=subscription.minutes_quota,
            clip_quota=subscription.clip_quota,
            retell_quota=subscription.retell_quota,
            storage_quota_gb=subscription.storage_quota_gb,
            renews_at=subscription.renews_at,
            canceled_at=subscription.canceled_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return subscription

    async def update_subscription(
        self, org_id: UUID, payload: SubscriptionUpdateRequest
    ) -> Subscription:
        model = await self._get_subscription_model(org_id)
        if not model:
            await self.get_subscription(org_id)
            model = await self._get_subscription_model(org_id)
            if not model:
                raise RuntimeError("Failed to initialise subscription")
        subscription = self._model_to_subscription(model)
        updates = payload.model_dump(exclude_unset=True)
        subscription = subscription.model_copy(update=updates)
        if "plan" in updates or "seats" in updates:
            subscription = plans.apply_plan(
                subscription,
                updates.get("plan", subscription.plan),
                updates.get("seats", subscription.seats),
            )
        subscription = subscription.model_copy(update={"updated_at": datetime.utcnow()})

        model.plan = subscription.plan.value
        model.status = subscription.status.value
        model.seats = subscription.seats
        model.minutes_quota = subscription.minutes_quota
        model.clip_quota = subscription.clip_quota
        model.retell_quota = subscription.retell_quota
        model.storage_quota_gb = subscription.storage_quota_gb
        model.renews_at = subscription.renews_at
        model.canceled_at = subscription.canceled_at
        model.updated_at = subscription.updated_at
        await self._session.commit()
        await self._session.refresh(model)
        return self._model_to_subscription(model)

    async def _get_usage_model(self, org_id: UUID) -> UsageModel:
        result = await self._session.execute(
            select(UsageModel).where(UsageModel.org_id == org_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return model
        model = UsageModel(org_id=org_id)
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_usage(self, org_id: UUID) -> UsageSnapshot:
        subscription = await self.get_subscription(org_id)
        model = await self._get_usage_model(org_id)
        await self._session.commit()
        return UsageSnapshot(
            minutes_processed=model.minutes_processed,
            minutes_quota=subscription.minutes_quota,
            clips_generated=model.clips_generated,
            clip_quota=subscription.clip_quota,
            retells_created=model.retells_created,
            retell_quota=subscription.retell_quota,
            storage_gb=model.storage_gb,
            storage_quota_gb=subscription.storage_quota_gb,
            updated_at=model.updated_at,
        )

    async def record_usage(
        self, org_id: UUID, payload: UsageIncrementRequest
    ) -> UsageSnapshot:
        model = await self._get_usage_model(org_id)
        data = payload.model_dump()
        model.minutes_processed += data["minutes_processed"]
        model.clips_generated += data["clips_generated"]
        model.retells_created += data["retells_created"]
        model.storage_gb += data["storage_gb"]
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        return await self.get_usage(org_id)

    async def save_payment_transaction(
        self, org_id: UUID, transaction: PaymentTransaction
    ) -> PaymentTransaction:
        existing = await self._session.execute(
            select(PaymentTransactionModel).where(
                PaymentTransactionModel.order_id == transaction.order_id
            )
        )
        model = existing.scalar_one_or_none()
        if model is None:
            model = PaymentTransactionModel(order_id=transaction.order_id, org_id=org_id)
            self._session.add(model)
        model.plan = transaction.plan.value
        model.seats = transaction.seats
        model.gross_amount = transaction.gross_amount
        model.status = transaction.status.value
        model.raw_status = transaction.raw_status
        model.payment_type = transaction.payment_type
        model.transaction_time = transaction.transaction_time
        model.transaction_id = transaction.transaction_id
        model.redirect_url = transaction.redirect_url
        model.snap_token = transaction.snap_token
        model.customer_email = transaction.customer_email
        model.customer_name = transaction.customer_name
        model.customer_phone = transaction.customer_phone
        model.fraud_status = transaction.fraud_status
        model.metadata = transaction.metadata
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return PaymentTransaction.model_validate(model)

    async def get_payment_transaction(
        self, org_id: UUID, order_id: str
    ) -> PaymentTransaction | None:
        result = await self._session.execute(
            select(PaymentTransactionModel).where(
                PaymentTransactionModel.order_id == order_id,
                PaymentTransactionModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return PaymentTransaction.model_validate(model)

    async def list_payment_transactions(
        self, org_id: UUID
    ) -> list[PaymentTransaction]:
        result = await self._session.execute(
            select(PaymentTransactionModel)
            .where(PaymentTransactionModel.org_id == org_id)
            .order_by(PaymentTransactionModel.created_at.desc())
        )
        return [PaymentTransaction.model_validate(row) for row in result.scalars().all()]

    async def get_org_id_for_order(self, order_id: str) -> UUID | None:
        result = await self._session.execute(
            select(PaymentTransactionModel.org_id).where(
                PaymentTransactionModel.order_id == order_id
            )
        )
        org_id = result.scalar_one_or_none()
        return org_id

    async def activate_subscription_from_payment(
        self, org_id: UUID, plan: PlanTier, seats: int
    ) -> Subscription:
        subscription = await self.get_subscription(org_id)
        subscription = plans.apply_plan(subscription, plan, seats)
        subscription = plans.mark_subscription_active(subscription)
        subscription = subscription.model_copy(
            update={
                "renews_at": plans.compute_renewal_at(),
                "updated_at": datetime.utcnow(),
                "canceled_at": None,
            }
        )
        model = await self._get_subscription_model(org_id)
        if not model:
            raise RuntimeError("Subscription record missing for organization")
        model.plan = subscription.plan.value
        model.status = subscription.status.value
        model.seats = subscription.seats
        model.minutes_quota = subscription.minutes_quota
        model.clip_quota = subscription.clip_quota
        model.retell_quota = subscription.retell_quota
        model.storage_quota_gb = subscription.storage_quota_gb
        model.renews_at = subscription.renews_at
        model.canceled_at = subscription.canceled_at
        model.updated_at = subscription.updated_at
        await self._session.commit()
        await self._session.refresh(model)
        return subscription
