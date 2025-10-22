"""Midtrans payment gateway integration helpers."""

from __future__ import annotations

from anyio import to_thread
import hashlib
import hmac
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

import midtransclient

from ..core import plans
from ..core.config import get_settings
from ..domain.billing import (
    PaymentNotificationRequest,
    PaymentStatus,
    PaymentTransaction,
    PaymentRequest,
)


class MidtransConfigError(RuntimeError):
    """Raised when Midtrans configuration is missing or invalid."""


class MidtransAPIError(RuntimeError):
    """Raised when Midtrans returns an error response."""


class MidtransGateway:
    """Wrapper around the Midtrans Snap and Core API clients."""

    def __init__(
        self,
        server_key: str,
        client_key: str,
        is_production: bool,
        app_name: str,
    ) -> None:
        if not server_key or not client_key:
            raise MidtransConfigError("Midtrans credentials are not configured")
        self._server_key = server_key
        self._client_key = client_key
        self._snap = midtransclient.Snap(
            is_production=is_production,
            server_key=server_key,
            client_key=client_key,
        )
        self._core = midtransclient.CoreApi(
            is_production=is_production,
            server_key=server_key,
            client_key=client_key,
        )
        self._app_name = app_name

    @property
    def client_key(self) -> str:
        return self._client_key

    def generate_order_id(self, org_id: UUID) -> str:
        """Generate a deterministic order id prefix for the given organization."""

        return f"{org_id.hex}-{uuid4().hex}"

    async def create_subscription_payment(
        self,
        org_id: UUID,
        payload: PaymentRequest,
    ) -> PaymentTransaction:
        settings = get_settings()
        amount = plans.calculate_subscription_amount(payload.plan, payload.seats)
        if amount <= 0:
            raise ValueError("Subscription amount must be greater than zero for checkout")
        gross_amount = plans.as_decimal_idr(amount)
        order_id = self.generate_order_id(org_id)
        unit_price = amount // payload.seats
        midtrans_payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": amount,
            },
            "item_details": [
                {
                    "id": payload.plan.value,
                    "price": unit_price,
                    "quantity": payload.seats,
                    "name": f"{settings.project_name} {payload.plan.value.title()} Plan",
                }
            ],
            "customer_details": {
                "first_name": payload.customer_name,
                "email": payload.customer_email,
                "phone": payload.customer_phone,
            },
            "callbacks": {
                "finish": str(payload.success_redirect_url),
                "error": str(payload.failure_redirect_url or payload.success_redirect_url),
            },
            "metadata": payload.metadata,
            "credit_card": {"secure": True},
            "custom_field1": self._app_name,
            "custom_field2": str(org_id),
        }

        try:
            response = await to_thread.run_sync(self._snap.create_transaction, midtrans_payload)
        except Exception as exc:  # pragma: no cover - network error bubble up
            raise MidtransAPIError("Failed to create Midtrans transaction") from exc

        return PaymentTransaction(
            order_id=order_id,
            org_id=org_id,
            plan=payload.plan,
            seats=payload.seats,
            gross_amount=gross_amount,
            status=PaymentStatus.PENDING,
            raw_status="pending",
            redirect_url=response.get("redirect_url"),
            snap_token=response.get("token"),
            customer_email=payload.customer_email,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            metadata=payload.metadata,
        )

    async def refresh_transaction(
        self, transaction: PaymentTransaction
    ) -> PaymentTransaction:
        try:
            response: Mapping[str, Any] = await to_thread.run_sync(
                self._core.transactions.status, transaction.order_id
            )
        except Exception as exc:  # pragma: no cover - network error bubble up
            raise MidtransAPIError("Failed to fetch Midtrans status") from exc

        return self._merge_transaction(transaction, response)

    def apply_notification(
        self,
        payload: PaymentNotificationRequest,
        current: PaymentTransaction,
    ) -> PaymentTransaction:
        response = {
            "transaction_status": payload.transaction_status,
            "payment_type": payload.payment_type,
            "transaction_time": payload.transaction_time.isoformat()
            if payload.transaction_time
            else None,
            "transaction_id": payload.transaction_id,
            "gross_amount": payload.gross_amount,
            "fraud_status": payload.fraud_status,
        }
        return self._merge_transaction(current, response)

    def verify_signature(self, payload: PaymentNotificationRequest) -> bool:
        message = (payload.order_id + payload.status_code + payload.gross_amount + self._server_key).encode()
        expected = hashlib.sha512(message).hexdigest()
        return hmac.compare_digest(expected, payload.signature_key)

    def _merge_transaction(
        self, transaction: PaymentTransaction, response: Mapping[str, Any]
    ) -> PaymentTransaction:
        raw_status = response.get("transaction_status", transaction.raw_status)
        status = self._map_status(raw_status)
        gross_amount = response.get("gross_amount")
        amount = (
            self._parse_amount(gross_amount)
            if gross_amount is not None
            else transaction.gross_amount
        )
        payment_type = response.get("payment_type", transaction.payment_type)
        fraud_status = response.get("fraud_status", transaction.fraud_status)
        transaction_time = response.get("transaction_time")
        parsed_time = self._parse_transaction_time(transaction_time) if transaction_time else transaction.transaction_time
        transaction_id = response.get("transaction_id", transaction.transaction_id)
        return transaction.model_copy(
            update={
                "status": status,
                "raw_status": raw_status,
                "gross_amount": amount,
                "payment_type": payment_type,
                "fraud_status": fraud_status,
                "transaction_time": parsed_time,
                "transaction_id": transaction_id,
            }
        )

    @staticmethod
    def _map_status(raw_status: str) -> PaymentStatus:
        match raw_status:
            case "capture" | "settlement":
                return PaymentStatus.SUCCESS
            case "pending":
                return PaymentStatus.PENDING
            case "cancel":
                return PaymentStatus.CANCELED
            case "expire":
                return PaymentStatus.EXPIRED
            case "refund" | "partial_refund":
                return PaymentStatus.REFUNDED
            case "chargeback" | "partial_chargeback":
                return PaymentStatus.CHARGEBACK
            case _:
                return PaymentStatus.FAILED

    @staticmethod
    def _parse_amount(amount: str | int | Decimal) -> Decimal:
        if isinstance(amount, Decimal):
            return amount
        if isinstance(amount, int):
            return Decimal(amount)
        sanitized = amount.replace(",", "") if isinstance(amount, str) else str(amount)
        return Decimal(sanitized)

    @staticmethod
    def _parse_transaction_time(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def build_gateway_from_settings() -> MidtransGateway:
    settings = get_settings()
    if not settings.midtrans_server_key or not settings.midtrans_client_key:
        raise MidtransConfigError(
            "Midtrans credentials must be configured via MIDTRANS_SERVER_KEY and MIDTRANS_CLIENT_KEY"
        )
    return MidtransGateway(
        server_key=settings.midtrans_server_key,
        client_key=settings.midtrans_client_key,
        is_production=settings.midtrans_is_production,
        app_name=settings.midtrans_app_name,
    )
