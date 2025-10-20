from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.billing import (
    PaymentListResponse,
    PaymentNotificationRequest,
    PaymentRequest,
    PaymentTransactionResponse,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    UsageIncrementRequest,
    UsageResponse,
)
from ...repositories.billing import BillingRepository
from ...domain.organizations import MembershipRole
from ..dependencies import (
    get_active_membership,
    get_billing_repository,
    get_org_id,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_midtrans_gateway,
)
from ...services.midtrans import MidtransAPIError, MidtransGateway

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def get_subscription(
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
) -> SubscriptionResponse:
    subscription = await billing_repo.get_subscription(org_id)
    return SubscriptionResponse(data=subscription)


@router.put(
    "/subscription",
    response_model=SubscriptionResponse,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def update_subscription(
    payload: SubscriptionUpdateRequest,
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
) -> SubscriptionResponse:
    subscription = await billing_repo.update_subscription(org_id, payload)
    return SubscriptionResponse(data=subscription)


@router.get(
    "/usage",
    response_model=UsageResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_usage(
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
) -> UsageResponse:
    usage = await billing_repo.get_usage(org_id)
    return UsageResponse(data=usage)


@router.post(
    "/usage",
    response_model=UsageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def record_usage(
    payload: UsageIncrementRequest,
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("billing:usage", limit=120, window_seconds=60)),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> UsageResponse:
    cached = idempotency.get_response(UsageResponse)
    if cached:
        return cached
    usage = await billing_repo.record_usage(org_id, payload)
    response = UsageResponse(data=usage)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.post(
    "/payments",
    response_model=PaymentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def create_payment_intent(
    payload: PaymentRequest,
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
    midtrans: MidtransGateway = Depends(get_midtrans_gateway),
    _: object = Depends(enforce_rate_limit("billing:payments", limit=30, window_seconds=60)),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> PaymentTransactionResponse:
    cached = idempotency.get_response(PaymentTransactionResponse)
    if cached:
        return cached
    try:
        transaction = await midtrans.create_subscription_payment(org_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MidtransAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    stored = await billing_repo.save_payment_transaction(org_id, transaction)
    response = PaymentTransactionResponse(
        data=stored,
        client_key=midtrans.client_key,
    )
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/payments",
    response_model=PaymentListResponse,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def list_payments(
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
    midtrans: MidtransGateway = Depends(get_midtrans_gateway),
) -> PaymentListResponse:
    payments = await billing_repo.list_payment_transactions(org_id)
    return PaymentListResponse(data=payments, client_key=midtrans.client_key)


@router.get(
    "/payments/{order_id}",
    response_model=PaymentTransactionResponse,
    dependencies=[
        Depends(
            require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
        )
    ],
)
async def get_payment(
    order_id: str,
    billing_repo: BillingRepository = Depends(get_billing_repository),
    org_id: UUID = Depends(get_org_id),
    midtrans: MidtransGateway = Depends(get_midtrans_gateway),
) -> PaymentTransactionResponse:
    transaction = await billing_repo.get_payment_transaction(org_id, order_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    try:
        refreshed = await midtrans.refresh_transaction(transaction)
    except MidtransAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    stored = await billing_repo.save_payment_transaction(org_id, refreshed)
    if stored.status.is_success:
        await billing_repo.activate_subscription_from_payment(org_id, stored.plan, stored.seats)
    return PaymentTransactionResponse(data=stored, client_key=midtrans.client_key)


@router.post("/payments/notifications", status_code=status.HTTP_200_OK)
async def handle_midtrans_notification(
    payload: PaymentNotificationRequest,
    billing_repo: BillingRepository = Depends(get_billing_repository),
    midtrans: MidtransGateway = Depends(get_midtrans_gateway),
) -> dict[str, str]:
    if not midtrans.verify_signature(payload):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    org_id = await billing_repo.get_org_id_for_order(payload.order_id)
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown order")
    transaction = await billing_repo.get_payment_transaction(org_id, payload.order_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    updated = midtrans.apply_notification(payload, transaction)
    stored = await billing_repo.save_payment_transaction(org_id, updated)
    if stored.status.is_success:
        await billing_repo.activate_subscription_from_payment(org_id, stored.plan, stored.seats)
    return {"status": "ok"}
