from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ...domain.audit import AuditLogCreate, AuditLogListResponse, AuditLogResponse
from ...domain.organizations import Membership, MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.users import User
from ...repositories.audit import AuditLogsRepository
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_active_membership,
    get_audit_logs_repository,
    get_current_user,
    get_org_id,
    require_org_role,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post(
    "/logs",
    response_model=AuditLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_audit_log(
    payload: AuditLogCreate,
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(get_active_membership),
    current_user: User = Depends(get_current_user),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> AuditLogResponse:
    cached = idempotency.get_response(AuditLogResponse)
    if cached:
        return cached
    event = await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=payload,
    )
    response = AuditLogResponse(data=event)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)),
    ],
)
async def list_audit_logs(
    target_id: UUID | None = Query(default=None),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> AuditLogListResponse:
    if target_id is not None:
        logs = await audit_repo.list_for_target(org_id=org_id, target_id=target_id)
    else:
        logs = await audit_repo.list_for_org(org_id=org_id)
    paginated, meta = paginate_sequence(logs, pagination)
    return AuditLogListResponse(data=paginated, count=meta.count, pagination=meta)
