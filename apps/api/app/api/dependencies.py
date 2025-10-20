from __future__ import annotations

from uuid import UUID

from collections.abc import Callable
from typing import Generic, Type, TypeVar

from fastapi import Depends, Header, HTTPException, Query, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.security import decode_access_token
from ..db import get_session, get_sessionmaker
from ..repositories.projects import (
    ProjectsRepository,
    SqlAlchemyProjectsRepository,
)
from ..repositories.branding import (
    BrandKitRepository,
    SqlAlchemyBrandKitRepository,
)
from ..repositories.videos import VideosRepository, SqlAlchemyVideosRepository
from ..repositories.jobs import JobsRepository, SqlAlchemyJobsRepository
from ..repositories.clips import ClipsRepository, SqlAlchemyClipsRepository
from ..repositories.retells import RetellsRepository, SqlAlchemyRetellsRepository
from ..repositories.artifacts import (
    ArtifactsRepository,
    SqlAlchemyArtifactsRepository,
)
from ..repositories.audit import AuditLogsRepository, SqlAlchemyAuditLogsRepository
from ..repositories.billing import BillingRepository, SqlAlchemyBillingRepository
from ..repositories.users import SqlAlchemyUsersRepository, UsersRepository
from ..domain.users import User
from ..domain.pagination import PaginationParams
from ..repositories.organizations import (
    SqlAlchemyOrganizationsRepository,
    OrganizationsRepository,
)
from ..repositories.transcripts import (
    TranscriptsRepository,
    SqlAlchemyTranscriptsRepository,
)
from ..repositories.observability import (
    ObservabilityRepository,
    SqlAlchemyObservabilityRepository,
)
from ..repositories.qa import QARunRepository, SqlAlchemyQARunRepository
from ..repositories.dmca import DmcaNoticesRepository, SqlAlchemyDmcaNoticesRepository
from ..repositories.rate_limits import (
    RateLimitRepository,
    SqlAlchemyRateLimitRepository,
)
from ..repositories.idempotency import (
    IdempotencyRepository,
    SqlAlchemyIdempotencyRepository,
)
from ..repositories.webhooks import (
    WebhookEndpointsRepository,
    SqlAlchemyWebhookEndpointsRepository,
)
from ..services.job_events import JobEventBroker
from ..services.midtrans import (
    MidtransConfigError,
    MidtransGateway,
    build_gateway_from_settings,
)
from ..services.storage import (
    MinioStorageService,
    StorageConfigurationError,
    build_storage_service,
)
from ..services.tasks import (
    TaskDispatcher,
    TaskQueueConfigurationError,
    build_task_dispatcher,
)
from ..domain.organizations import Membership, MembershipRole, MembershipStatus
from ..domain.rate_limits import RateLimitExceededPayload, RateLimitStatus
from ..domain.idempotency import IdempotencyRecord
from pydantic import BaseModel

T_Model = TypeVar("T_Model", bound=BaseModel)

_job_events = JobEventBroker()
_http_bearer = HTTPBearer(auto_error=False)
_midtrans_gateway: MidtransGateway | None = None
_storage_service: MinioStorageService | None = None
_task_dispatcher: TaskDispatcher | None = None


def _resolve_org_id(raw_value: str | None) -> UUID:
    settings = get_settings()
    org_id = raw_value or settings.default_org_id
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization header missing",
        )
    try:
        return UUID(org_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization identifier",
        ) from exc


async def get_projects_repository(
    session: AsyncSession = Depends(get_session),
) -> ProjectsRepository:
    return SqlAlchemyProjectsRepository(session)


async def get_brand_kit_repository(
    session: AsyncSession = Depends(get_session),
) -> BrandKitRepository:
    return SqlAlchemyBrandKitRepository(session)


async def get_videos_repository(
    session: AsyncSession = Depends(get_session),
) -> VideosRepository:
    return SqlAlchemyVideosRepository(session)


async def get_jobs_repository(
    session: AsyncSession = Depends(get_session),
) -> JobsRepository:
    return SqlAlchemyJobsRepository(session)


async def get_clips_repository(
    session: AsyncSession = Depends(get_session),
) -> ClipsRepository:
    return SqlAlchemyClipsRepository(session)


async def get_retells_repository(
    session: AsyncSession = Depends(get_session),
) -> RetellsRepository:
    return SqlAlchemyRetellsRepository(session)


async def get_artifacts_repository(
    session: AsyncSession = Depends(get_session),
) -> ArtifactsRepository:
    return SqlAlchemyArtifactsRepository(session)


async def get_audit_logs_repository(
    session: AsyncSession = Depends(get_session),
) -> AuditLogsRepository:
    return SqlAlchemyAuditLogsRepository(session)


async def get_transcripts_repository(
    session: AsyncSession = Depends(get_session),
) -> TranscriptsRepository:
    return SqlAlchemyTranscriptsRepository(session)


async def get_job_event_broker() -> JobEventBroker:
    return _job_events


async def get_billing_repository(
    session: AsyncSession = Depends(get_session),
) -> BillingRepository:
    return SqlAlchemyBillingRepository(session)


async def get_users_repository(
    session: AsyncSession = Depends(get_session),
) -> UsersRepository:
    return SqlAlchemyUsersRepository(session)


async def get_organizations_repository(
    session: AsyncSession = Depends(get_session),
) -> OrganizationsRepository:
    return SqlAlchemyOrganizationsRepository(session)


async def get_observability_repository(
    session: AsyncSession = Depends(get_session),
) -> ObservabilityRepository:
    return SqlAlchemyObservabilityRepository(session)


async def get_qa_run_repository(
    session: AsyncSession = Depends(get_session),
) -> QARunRepository:
    return SqlAlchemyQARunRepository(session)


async def get_dmca_notices_repository(
    session: AsyncSession = Depends(get_session),
) -> DmcaNoticesRepository:
    return SqlAlchemyDmcaNoticesRepository(session)


async def get_rate_limit_repository(
    session: AsyncSession = Depends(get_session),
) -> RateLimitRepository:
    return SqlAlchemyRateLimitRepository(session)


async def get_idempotency_repository(
    session: AsyncSession = Depends(get_session),
) -> IdempotencyRepository:
    return SqlAlchemyIdempotencyRepository(session)


async def get_webhook_endpoints_repository(
    session: AsyncSession = Depends(get_session),
) -> WebhookEndpointsRepository:
    return SqlAlchemyWebhookEndpointsRepository(session)


async def get_pagination_params(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginationParams:
    return PaginationParams(limit=limit, offset=offset)


async def get_midtrans_gateway() -> MidtransGateway:
    global _midtrans_gateway
    if _midtrans_gateway is None:
        try:
            _midtrans_gateway = build_gateway_from_settings()
        except MidtransConfigError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    return _midtrans_gateway


async def get_storage_service() -> MinioStorageService:
    global _storage_service
    if _storage_service is None:
        try:
            _storage_service = build_storage_service()
        except StorageConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    return _storage_service


async def get_task_dispatcher() -> TaskDispatcher:
    global _task_dispatcher
    if _task_dispatcher is None:
        try:
            _task_dispatcher = build_task_dispatcher()
        except TaskQueueConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    return _task_dispatcher


async def get_org_id(
    x_org_id: str | None = Header(default=None, alias="X-Org-ID"),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> UUID:
    org_id = _resolve_org_id(x_org_id)
    org = await orgs_repo.get(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org_id


async def require_worker_token(
    worker_token: str | None = Header(default=None, alias="X-Worker-Token")
) -> None:
    settings = get_settings()
    expected = settings.worker_service_token
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker token is not configured",
        )
    if worker_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token",
        )


async def get_org_id_from_websocket(websocket: WebSocket) -> UUID:
    header_value = websocket.headers.get("X-Org-ID")
    if header_value is None:
        header_value = websocket.query_params.get("org_id")
    org_id = _resolve_org_id(header_value)
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = SqlAlchemyOrganizationsRepository(session)
        org = await repo.get(org_id)
    if org is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org_id


async def get_current_user_from_websocket(websocket: WebSocket) -> User:
    token = None
    auth_header = websocket.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if token is None:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authenticated")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    subject = payload.get("sub")
    if subject is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = SqlAlchemyUsersRepository(session)
        user = await repo.get(user_id)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def ensure_websocket_membership(
    websocket: WebSocket,
) -> tuple[UUID, Membership]:
    org_id = await get_org_id_from_websocket(websocket)
    user = await get_current_user_from_websocket(websocket)
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = SqlAlchemyOrganizationsRepository(session)
        membership = await repo.find_membership_by_user(org_id, user.id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not authorized")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership inactive",
        )
    return org_id, membership


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    users_repo: UsersRepository = Depends(get_users_repository),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    user = await users_repo.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_active_membership(
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
    orgs_repo: OrganizationsRepository = Depends(get_organizations_repository),
) -> Membership:
    membership = await orgs_repo.find_membership_by_user(org_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership required",
        )
    if membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership inactive",
        )
    return membership


def require_org_role(*roles: MembershipRole) -> Callable[[Membership], Membership]:
    allowed_roles = set(roles)

    async def dependency(
        membership: Membership = Depends(get_active_membership),
    ) -> Membership:
        if allowed_roles and membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return membership

    return dependency


def enforce_rate_limit(
    scope: str,
    *,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> Callable[[RateLimitRepository], RateLimitStatus]:
    """Dependency factory that enforces per-member quotas for a scope."""

    async def dependency(
        membership: Membership = Depends(get_active_membership),
        repo: RateLimitRepository = Depends(get_rate_limit_repository),
    ) -> RateLimitStatus:
        settings = get_settings()
        effective_limit = limit or settings.rate_limit_requests_per_minute
        effective_window = window_seconds or settings.rate_limit_window_seconds
        status = await repo.hit(
            scope=scope,
            key=f"{membership.org_id}:{membership.user_id}",
            limit=effective_limit,
            window_seconds=effective_window,
        )
        if not status.allowed:
            payload = RateLimitExceededPayload(
                limit=status.limit,
                retry_after=status.retry_after_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=payload.model_dump(),
            )
        return status
    
    return dependency


class IdempotencyContext(Generic[T_Model]):
    """Tracks the idempotency state for a request."""

    def __init__(
        self,
        *,
        key: str | None,
        org_id: UUID,
        method: str,
        path: str,
        repository: IdempotencyRepository,
        record: IdempotencyRecord | None,
    ) -> None:
        self._key = key
        self._org_id = org_id
        self._method = method
        self._path = path
        self._repository = repository
        self._record = record

    @property
    def enabled(self) -> bool:
        return self._key is not None

    @property
    def has_response(self) -> bool:
        return self._record is not None

    def get_response(self, model_type: Type[T_Model]) -> T_Model | None:
        if not self._record:
            return None
        return model_type.model_validate(self._record.payload)

    def get_status_code(self) -> int | None:
        if not self._record:
            return None
        return self._record.status_code

    def get_payload(self) -> dict[str, object] | None:
        if not self._record:
            return None
        return self._record.payload

    async def store_response(
        self,
        payload: BaseModel | dict[str, object],
        *,
        status_code: int,
    ) -> None:
        if not self.enabled or self._record is not None or self._key is None:
            return
        record = IdempotencyRecord(
            org_id=self._org_id,
            key=self._key,
            method=self._method,
            path=self._path,
            status_code=status_code,
            payload=jsonable_encoder(payload),
        )
        self._record = await self._repository.save(record)


async def get_idempotency_context(
    request: Request,
    key: str | None = Header(default=None, alias="Idempotency-Key"),
    org_id: UUID = Depends(get_org_id),
    repo: IdempotencyRepository = Depends(get_idempotency_repository),
) -> IdempotencyContext:
    record = None
    if key:
        record = await repo.get(org_id=org_id, key=key)
        if record and (record.method != request.method or record.path != request.url.path):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key used with a different request",
            )
    return IdempotencyContext(
        key=key,
        org_id=org_id,
        method=request.method,
        path=request.url.path,
        repository=repo,
        record=record,
    )
