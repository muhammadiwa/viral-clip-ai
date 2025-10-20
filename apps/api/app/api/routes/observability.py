from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder

from ...domain.observability import (
    MetricCreate,
    MetricListResponse,
    MetricResponse,
    MetricSummaryResponse,
    SLOReportResponse,
)
from ...domain.qa import (
    QAFindingCreate,
    QAFindingListResponse,
    QAFindingResponse,
    QAFindingStatus,
    QAFindingUpdate,
    QAReviewCreate,
    QAReviewListResponse,
    QAReviewResponse,
    QAReviewUpdate,
    QARunCreate,
    QARunListResponse,
    QARunResponse,
)
from ...domain.pagination import PaginationMeta, PaginationParams
from ...domain.organizations import MembershipRole, MembershipStatus
from ...domain.webhooks import WebhookEventType
from ...repositories.observability import ObservabilityRepository
from ...repositories.qa import QARunRepository
from ...repositories.webhooks import WebhookEndpointsRepository
from ...repositories.users import UsersRepository
from ...repositories.organizations import OrganizationsRepository
from ...services.pagination import paginate_sequence

_ALLOWED_FINDING_TRANSITIONS: dict[QAFindingStatus, set[QAFindingStatus]] = {
    QAFindingStatus.OPEN: {
        QAFindingStatus.ACKNOWLEDGED,
        QAFindingStatus.IN_PROGRESS,
        QAFindingStatus.BLOCKED,
        QAFindingStatus.READY_FOR_REVIEW,
        QAFindingStatus.RESOLVED,
    },
    QAFindingStatus.ACKNOWLEDGED: {
        QAFindingStatus.OPEN,
        QAFindingStatus.IN_PROGRESS,
        QAFindingStatus.BLOCKED,
        QAFindingStatus.READY_FOR_REVIEW,
        QAFindingStatus.RESOLVED,
    },
    QAFindingStatus.IN_PROGRESS: {
        QAFindingStatus.ACKNOWLEDGED,
        QAFindingStatus.BLOCKED,
        QAFindingStatus.READY_FOR_REVIEW,
        QAFindingStatus.RESOLVED,
    },
    QAFindingStatus.BLOCKED: {
        QAFindingStatus.ACKNOWLEDGED,
        QAFindingStatus.IN_PROGRESS,
        QAFindingStatus.READY_FOR_REVIEW,
    },
    QAFindingStatus.READY_FOR_REVIEW: {
        QAFindingStatus.ACKNOWLEDGED,
        QAFindingStatus.IN_PROGRESS,
        QAFindingStatus.BLOCKED,
        QAFindingStatus.RESOLVED,
    },
    QAFindingStatus.RESOLVED: {
        QAFindingStatus.ACKNOWLEDGED,
        QAFindingStatus.OPEN,
    },
}


def _validate_status_transition(
    current: QAFindingStatus, new_status: QAFindingStatus
) -> None:
    if current == new_status:
        return
    allowed = _ALLOWED_FINDING_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid QA finding status transition",
        )
from ..dependencies import (
    get_active_membership,
    get_observability_repository,
    get_qa_run_repository,
    get_org_id,
    get_webhook_endpoints_repository,
    require_org_role,
    enforce_rate_limit,
    get_pagination_params,
    get_users_repository,
    get_organizations_repository,
)

async def _resolve_assignee_metadata(
    *,
    assignee_id: UUID | None,
    assignee_name: str | None,
    org_id: UUID,
    users_repo: UsersRepository,
    orgs_repo: OrganizationsRepository,
    assigned_at: datetime | None = None,
) -> tuple[UUID | None, str | None, datetime | None]:
    if assignee_id is None:
        return None, None, None
    user = await users_repo.get(assignee_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignee user not found",
        )
    membership = await orgs_repo.find_membership_by_user(org_id, assignee_id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be an active member of this organization",
        )
    resolved_name = assignee_name or user.full_name or user.email
    timestamp = assigned_at or datetime.utcnow()
    return assignee_id, resolved_name, timestamp


router = APIRouter(prefix="/observability", tags=["observability"])


@router.post(
    "/metrics",
    response_model=MetricResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def record_metric(
    payload: MetricCreate,
    repo: ObservabilityRepository = Depends(get_observability_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("observability:metrics", limit=60, window_seconds=60)),
) -> MetricResponse:
    metric = await repo.record_metric(org_id, payload)
    return MetricResponse(data=metric)


@router.get(
    "/metrics",
    response_model=MetricListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_metrics(
    name: str | None = Query(default=None, min_length=3, max_length=128),
    repo: ObservabilityRepository = Depends(get_observability_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> MetricListResponse:
    fetch_limit = pagination.offset + pagination.limit
    metrics = await repo.list_metrics(org_id, name=name, limit=fetch_limit)
    paginated, meta = paginate_sequence(metrics, pagination)
    return MetricListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get(
    "/metrics/summary",
    response_model=MetricSummaryResponse,
    dependencies=[Depends(get_active_membership)],
)
async def summarize_metrics(
    name: str | None = Query(default=None, min_length=3, max_length=128),
    repo: ObservabilityRepository = Depends(get_observability_repository),
    org_id: UUID = Depends(get_org_id),
) -> MetricSummaryResponse:
    summary = await repo.summarize_metrics(org_id, name=name)
    return MetricSummaryResponse(data=summary)


@router.get(
    "/slo/job-completion",
    response_model=SLOReportResponse,
    dependencies=[Depends(get_active_membership)],
)
async def evaluate_job_completion_slo(
    target_seconds: float = Query(default=1800.0, gt=0),
    metric_name: str = Query(
        default="job.duration_seconds", min_length=3, max_length=128
    ),
    repo: ObservabilityRepository = Depends(get_observability_repository),
    org_id: UUID = Depends(get_org_id),
) -> SLOReportResponse:
    report = await repo.evaluate_slo(
        org_id,
        name=metric_name,
        target_value=target_seconds,
        unit="seconds",
    )
    return SLOReportResponse(data=report)


@router.post(
    "/qa-runs",
    response_model=QARunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def record_qa_run(
    payload: QARunCreate,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
) -> QARunResponse:
    run = await repo.record_run(org_id, payload)
    return QARunResponse(data=run)


@router.get(
    "/qa-runs/{run_id}",
    response_model=QARunResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_qa_run(
    run_id: UUID,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
) -> QARunResponse:
    run = await repo.get_run(org_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found")
    return QARunResponse(data=run)


@router.get(
    "/qa-runs",
    response_model=QARunListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_qa_runs(
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> QARunListResponse:
    runs = await repo.list_runs(
        org_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    total = await repo.count_runs(org_id)
    count = len(runs)
    has_more = pagination.offset + pagination.limit < total
    next_offset = (
        pagination.offset + pagination.limit if has_more else None
    )
    meta = PaginationMeta(
        limit=pagination.limit,
        offset=pagination.offset,
        count=count,
        total=total,
        has_more=has_more,
        next_offset=next_offset,
    )
    return QARunListResponse(data=runs, count=count, pagination=meta)


@router.post(
    "/qa-runs/{run_id}/findings",
    response_model=QAFindingListResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def add_qa_findings(
    run_id: UUID,
    findings: list[QAFindingCreate],
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> QAFindingListResponse:
    enriched: list[QAFindingCreate] = []
    for finding in findings:
        if finding.assignee_id is not None:
            assignee_id, assignee_name, assigned_at = await _resolve_assignee_metadata(
                assignee_id=finding.assignee_id,
                assignee_name=finding.assignee_name,
                assigned_at=finding.assigned_at,
                org_id=org_id,
                users_repo=users_repo,
                orgs_repo=orgs_repo,
            )
            finding = finding.model_copy(
                update={
                    "assignee_id": assignee_id,
                    "assignee_name": assignee_name,
                    "assigned_at": assigned_at,
                }
            )
        enriched.append(finding)
    created = await repo.create_findings(
        org_id=org_id, run_id=run_id, findings=enriched
    )
    for finding in created:
        await webhooks_repo.publish_event(
            org_id=org_id,
            event_type=WebhookEventType.QA_FINDING_UPDATED,
            payload={
                "run_id": str(run_id),
                "finding": jsonable_encoder(finding, exclude_none=True),
            },
        )
        if finding.assignee_id is not None or finding.due_date is not None:
            await webhooks_repo.publish_event(
                org_id=org_id,
                event_type=WebhookEventType.QA_ASSIGNMENT_UPDATED,
                payload={
                    "run_id": str(run_id),
                    "finding": jsonable_encoder(finding, exclude_none=True),
                },
            )
    return QAFindingListResponse(data=created, count=len(created))


@router.get(
    "/qa-runs/{run_id}/findings",
    response_model=QAFindingListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_qa_findings(
    run_id: UUID,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
) -> QAFindingListResponse:
    findings = await repo.list_findings(org_id, run_id)
    return QAFindingListResponse(data=findings, count=len(findings))


@router.patch(
    "/qa-runs/{run_id}/findings/{finding_id}",
    response_model=QAFindingResponse,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def update_qa_finding(
    run_id: UUID,
    finding_id: UUID,
    payload: QAFindingUpdate,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
    users_repo: UsersRepository = Depends(get_users_repository),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> QAFindingResponse:
    existing = await repo.get_finding(org_id, finding_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="QA finding not found"
        )
    if payload.status is not None:
        _validate_status_transition(existing.status, payload.status)
    if "assignee_id" in payload.model_fields_set:
        if payload.assignee_id is not None:
            assignee_id, assignee_name, assigned_at = await _resolve_assignee_metadata(
                assignee_id=payload.assignee_id,
                assignee_name=payload.assignee_name,
                assigned_at=payload.assigned_at,
                org_id=org_id,
                users_repo=users_repo,
                orgs_repo=orgs_repo,
            )
            payload = payload.model_copy(
                update={
                    "assignee_id": assignee_id,
                    "assignee_name": assignee_name,
                    "assigned_at": assigned_at,
                }
            )
        else:
            payload = payload.model_copy(
                update={
                    "assignee_name": None,
                    "assigned_at": None,
                }
            )
    updated = await repo.update_finding(org_id, finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA finding not found")
    await webhooks_repo.publish_event(
        org_id=org_id,
        event_type=WebhookEventType.QA_FINDING_UPDATED,
        payload={
            "run_id": str(run_id),
            "finding": jsonable_encoder(updated, exclude_none=True),
        },
    )
    if (
        existing.assignee_id != updated.assignee_id
        or existing.assignee_name != updated.assignee_name
        or existing.due_date != updated.due_date
    ):
        await webhooks_repo.publish_event(
            org_id=org_id,
            event_type=WebhookEventType.QA_ASSIGNMENT_UPDATED,
            payload={
                "run_id": str(run_id),
                "finding": jsonable_encoder(updated, exclude_none=True),
            },
        )
    return QAFindingResponse(data=updated)


@router.post(
    "/qa-runs/{run_id}/reviews",
    response_model=QAReviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def create_qa_review(
    run_id: UUID,
    payload: QAReviewCreate,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> QAReviewResponse:
    review = await repo.create_review(org_id, run_id, payload)
    await webhooks_repo.publish_event(
        org_id=org_id,
        event_type=WebhookEventType.QA_REVIEW_UPDATED,
        payload={
            "run_id": str(run_id),
            "review": jsonable_encoder(review, exclude_none=True),
        },
    )
    return QAReviewResponse(data=review)


@router.get(
    "/qa-runs/{run_id}/reviews",
    response_model=QAReviewListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_qa_reviews(
    run_id: UUID,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
) -> QAReviewListResponse:
    reviews = await repo.list_reviews(org_id, run_id)
    return QAReviewListResponse(data=reviews, count=len(reviews))


@router.patch(
    "/qa-runs/{run_id}/reviews/{review_id}",
    response_model=QAReviewResponse,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def update_qa_review(
    run_id: UUID,
    review_id: UUID,
    payload: QAReviewUpdate,
    repo: QARunRepository = Depends(get_qa_run_repository),
    org_id: UUID = Depends(get_org_id),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> QAReviewResponse:
    review = await repo.update_review(org_id, review_id, payload)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA review not found")
    await webhooks_repo.publish_event(
        org_id=org_id,
        event_type=WebhookEventType.QA_REVIEW_UPDATED,
        payload={
            "run_id": str(run_id),
            "review": jsonable_encoder(review, exclude_none=True),
        },
    )
    return QAReviewResponse(data=review)
