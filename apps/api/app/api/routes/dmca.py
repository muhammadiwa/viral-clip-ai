from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...domain.audit import AuditLogCreate
from ...domain.dmca import (
    DmcaNoticeCreate,
    DmcaNoticeListResponse,
    DmcaNoticeResponse,
    DmcaNoticeStatus,
    DmcaNoticeUpdateRequest,
)
from ...domain.organizations import Membership, MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.users import User
from ...repositories.audit import AuditLogsRepository
from ...repositories.dmca import DmcaNoticesRepository
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_active_membership,
    get_audit_logs_repository,
    get_current_user,
    get_dmca_notices_repository,
    get_org_id,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
)

router = APIRouter(prefix="/dmca", tags=["dmca"])


@router.post(
    "/notices",
    response_model=DmcaNoticeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_dmca_notice(
    payload: DmcaNoticeCreate,
    repo: DmcaNoticesRepository = Depends(get_dmca_notices_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(get_active_membership),
    current_user: User = Depends(get_current_user),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    _: object = Depends(enforce_rate_limit("dmca:submit", limit=5, window_seconds=3600)),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> DmcaNoticeResponse:
    cached = idempotency.get_response(DmcaNoticeResponse)
    if cached:
        return cached
    notice = await repo.create(org_id=org_id, payload=payload)
    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="dmca.notice.created",
            target_type="dmca_notice",
            target_id=notice.id,
            message="New DMCA notice submitted",
            metadata={
                "status": notice.status,
                "target_type": notice.target_type,
            },
        ),
    )
    response = DmcaNoticeResponse(data=notice)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/notices",
    response_model=DmcaNoticeListResponse,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def list_dmca_notices(
    status: DmcaNoticeStatus | None = Query(
        default=None,
        description="Optional status filter to scope notices",
    ),
    repo: DmcaNoticesRepository = Depends(get_dmca_notices_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> DmcaNoticeListResponse:
    notices = await repo.list_for_org(org_id=org_id, status=status)
    paginated, meta = paginate_sequence(notices, pagination)
    return DmcaNoticeListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get(
    "/notices/{notice_id}",
    response_model=DmcaNoticeResponse,
)
async def get_dmca_notice(
    notice_id: UUID,
    repo: DmcaNoticesRepository = Depends(get_dmca_notices_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(get_active_membership),
) -> DmcaNoticeResponse:
    _ = membership  # ensures active membership validation
    notice = await repo.get(notice_id=notice_id, org_id=org_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DMCA notice not found")
    return DmcaNoticeResponse(data=notice)


@router.patch(
    "/notices/{notice_id}",
    response_model=DmcaNoticeResponse,
    dependencies=[Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))],
)
async def update_dmca_notice(
    notice_id: UUID,
    payload: DmcaNoticeUpdateRequest,
    repo: DmcaNoticesRepository = Depends(get_dmca_notices_repository),
    org_id: UUID = Depends(get_org_id),
    membership: Membership = Depends(get_active_membership),
    current_user: User = Depends(get_current_user),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    _: object = Depends(enforce_rate_limit("dmca:update", limit=30, window_seconds=3600)),
) -> DmcaNoticeResponse:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates supplied",
        )
    notice = await repo.update(notice_id=notice_id, org_id=org_id, payload=payload)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DMCA notice not found")
    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="dmca.notice.updated",
            target_type="dmca_notice",
            target_id=notice.id,
            message=payload.reviewer_notes,
            metadata={
                "status": notice.status,
                "action_taken": notice.action_taken,
            },
        ),
    )
    return DmcaNoticeResponse(data=notice)
