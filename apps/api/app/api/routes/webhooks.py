from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...domain.audit import AuditLogCreate
from ...domain.organizations import Membership, MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.users import User
from ...domain.webhooks import (
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookDeliveryStatus,
    WebhookDeliveryUpdate,
    WebhookEndpointCreate,
    WebhookEndpointListResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
)
from ...repositories.audit import AuditLogsRepository
from ...repositories.webhooks import WebhookEndpointsRepository
from ...services.pagination import paginate_sequence
from ..dependencies import (
    IdempotencyContext,
    enforce_rate_limit,
    get_audit_logs_repository,
    get_current_user,
    get_idempotency_context,
    get_org_id,
    get_pagination_params,
    get_webhook_endpoints_repository,
    require_org_role,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/endpoints",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook_endpoint(
    payload: WebhookEndpointCreate,
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    _: object = Depends(enforce_rate_limit("webhooks:create", limit=20, window_seconds=3600)),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> WebhookEndpointResponse:
    cached = idempotency.get_response(WebhookEndpointResponse)
    if cached:
        return cached

    endpoint = await repo.create_endpoint(org_id=org_id, payload=payload)
    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="webhook.endpoint.created",
            target_type="webhook_endpoint",
            target_id=endpoint.id,
            message=f"Webhook endpoint {endpoint.name} created",
            metadata={
                "url": str(endpoint.url),
                "events": [event.value for event in endpoint.events],
            },
        ),
    )

    response = WebhookEndpointResponse(data=endpoint)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/endpoints",
    response_model=WebhookEndpointListResponse,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def list_webhook_endpoints(
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> WebhookEndpointListResponse:
    endpoints = await repo.list_endpoints(org_id=org_id)
    paginated, meta = paginate_sequence(endpoints, pagination)
    return WebhookEndpointListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def get_webhook_endpoint(
    endpoint_id: UUID,
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
) -> WebhookEndpointResponse:
    endpoint = await repo.get_endpoint(endpoint_id=endpoint_id, org_id=org_id)
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook endpoint not found")
    return WebhookEndpointResponse(data=endpoint)


@router.patch(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointResponse,
)
async def update_webhook_endpoint(
    endpoint_id: UUID,
    payload: WebhookEndpointUpdate,
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    _: object = Depends(enforce_rate_limit("webhooks:update", limit=60, window_seconds=3600)),
) -> WebhookEndpointResponse:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates supplied")

    endpoint = await repo.update_endpoint(
        endpoint_id=endpoint_id,
        org_id=org_id,
        payload=payload,
    )
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook endpoint not found")

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="webhook.endpoint.updated",
            target_type="webhook_endpoint",
            target_id=endpoint.id,
            message="Webhook endpoint updated",
            metadata=update_data,
        ),
    )

    return WebhookEndpointResponse(data=endpoint)


@router.get(
    "/deliveries",
    response_model=WebhookDeliveryListResponse,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def list_webhook_deliveries(
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
    endpoint_id: UUID | None = Query(default=None),
    status: WebhookDeliveryStatus | None = Query(default=None),
) -> WebhookDeliveryListResponse:
    deliveries = await repo.list_deliveries(
        org_id=org_id,
        endpoint_id=endpoint_id,
        status=status,
    )
    paginated, meta = paginate_sequence(deliveries, pagination)
    return WebhookDeliveryListResponse(data=paginated, count=meta.count, pagination=meta)


@router.patch(
    "/deliveries/{delivery_id}",
    response_model=WebhookDeliveryResponse,
)
async def update_webhook_delivery(
    delivery_id: UUID,
    payload: WebhookDeliveryUpdate,
    repo: WebhookEndpointsRepository = Depends(get_webhook_endpoints_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
) -> WebhookDeliveryResponse:
    delivery = await repo.update_delivery(
        delivery_id=delivery_id,
        org_id=org_id,
        status=payload.status,
        response_code=payload.response_code,
        error_message=payload.error_message,
    )
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook delivery not found")

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="webhook.delivery.updated",
            target_type="webhook_delivery",
            target_id=delivery.id,
            message="Webhook delivery status updated",
            metadata={
                "status": delivery.status,
                "response_code": delivery.response_code,
            },
        ),
    )

    return WebhookDeliveryResponse(data=delivery)

