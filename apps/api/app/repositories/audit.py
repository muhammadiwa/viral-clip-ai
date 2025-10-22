from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.audit import AuditLog, AuditLogCreate
from ..domain.organizations import MembershipRole
from ..models.audit import AuditLogModel


class AuditLogsRepository(Protocol):
    async def record(
        self,
        *,
        org_id: UUID,
        actor_id: UUID,
        actor_email: str | None,
        actor_role: MembershipRole | None,
        payload: AuditLogCreate,
    ) -> AuditLog:
        ...

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        ...

    async def list_for_target(
        self,
        *,
        org_id: UUID,
        target_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        ...


class InMemoryAuditLogsRepository:
    """In-memory storage backing audit log endpoints for early iterations."""

    def __init__(self) -> None:
        self._logs_by_org: dict[UUID, list[AuditLog]] = defaultdict(list)

    async def record(
        self,
        *,
        org_id: UUID,
        actor_id: UUID,
        actor_email: str | None,
        actor_role: MembershipRole | None,
        payload: AuditLogCreate,
    ) -> AuditLog:
        now = datetime.utcnow()
        metadata = payload.metadata or None
        entry = AuditLog(
            org_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            created_at=now,
            metadata=metadata,
            **payload.model_dump(exclude={"metadata"}),
        )
        self._logs_by_org[org_id].append(entry)
        # keep newest first for deterministic ordering
        self._logs_by_org[org_id].sort(key=lambda item: item.created_at, reverse=True)
        return entry

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        logs = list(self._logs_by_org.get(org_id, []))
        if limit is not None:
            return logs[:limit]
        return logs

    async def list_for_target(
        self,
        *,
        org_id: UUID,
        target_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        results = [
            log
            for log in self._logs_by_org.get(org_id, [])
            if log.target_id == target_id
        ]
        if limit is not None:
            return results[:limit]
        return results


class SqlAlchemyAuditLogsRepository(AuditLogsRepository):
    """Postgres-backed audit log repository implementation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        org_id: UUID,
        actor_id: UUID,
        actor_email: str | None,
        actor_role: MembershipRole | None,
        payload: AuditLogCreate,
    ) -> AuditLog:
        model = AuditLogModel(
            org_id=org_id,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role.value if actor_role else None,
            action=payload.action,
            target_type=payload.target_type,
            target_id=payload.target_id,
            target_display_name=payload.target_display_name,
            message=payload.message,
            metadata=payload.metadata,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return AuditLog.model_validate(model)

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        query = (
            select(AuditLogModel)
            .where(AuditLogModel.org_id == org_id)
            .order_by(AuditLogModel.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        return [AuditLog.model_validate(row) for row in result.scalars().all()]

    async def list_for_target(
        self,
        *,
        org_id: UUID,
        target_id: UUID,
        limit: int | None = None,
    ) -> list[AuditLog]:
        query = (
            select(AuditLogModel)
            .where(
                AuditLogModel.org_id == org_id,
                AuditLogModel.target_id == target_id,
            )
            .order_by(AuditLogModel.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        return [AuditLog.model_validate(row) for row in result.scalars().all()]
