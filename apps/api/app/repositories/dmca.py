from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.dmca import DmcaNotice, DmcaNoticeCreate, DmcaNoticeStatus, DmcaNoticeUpdateRequest
from ..models.dmca import DmcaNoticeModel


class DmcaNoticesRepository(Protocol):
    async def create(self, *, org_id: UUID, payload: DmcaNoticeCreate) -> DmcaNotice: ...

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        status: DmcaNoticeStatus | None = None,
    ) -> list[DmcaNotice]: ...

    async def get(self, *, notice_id: UUID, org_id: UUID) -> DmcaNotice | None: ...

    async def update(
        self,
        *,
        notice_id: UUID,
        org_id: UUID,
        payload: DmcaNoticeUpdateRequest,
    ) -> DmcaNotice | None: ...


class InMemoryDmcaNoticesRepository:
    """Ephemeral repository backing DMCA compliance endpoints in early development."""

    def __init__(self) -> None:
        self._notices_by_org: dict[UUID, dict[UUID, DmcaNotice]] = defaultdict(dict)

    async def create(self, *, org_id: UUID, payload: DmcaNoticeCreate) -> DmcaNotice:
        notice = DmcaNotice(org_id=org_id, **payload.model_dump())
        self._notices_by_org[org_id][notice.id] = notice
        return notice

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        status: DmcaNoticeStatus | None = None,
    ) -> list[DmcaNotice]:
        notices = list(self._notices_by_org.get(org_id, {}).values())
        if status is not None:
            notices = [notice for notice in notices if notice.status == status]
        notices.sort(key=lambda notice: notice.created_at, reverse=True)
        return notices

    async def get(self, *, notice_id: UUID, org_id: UUID) -> DmcaNotice | None:
        return self._notices_by_org.get(org_id, {}).get(notice_id)

    async def update(
        self,
        *,
        notice_id: UUID,
        org_id: UUID,
        payload: DmcaNoticeUpdateRequest,
    ) -> DmcaNotice | None:
        notice = await self.get(notice_id=notice_id, org_id=org_id)
        if notice is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] is not None:
            status = update_data["status"]
            update_data["status"] = status
            if status in (DmcaNoticeStatus.CONTENT_REMOVED, DmcaNoticeStatus.RESOLVED):
                update_data.setdefault("resolved_at", datetime.utcnow())
            elif status in (DmcaNoticeStatus.RECEIVED, DmcaNoticeStatus.UNDER_REVIEW):
                update_data["resolved_at"] = None
        updated = notice.model_copy(
            update={
                **update_data,
                "updated_at": datetime.utcnow(),
            }
        )
        self._notices_by_org[org_id][notice_id] = updated
        return updated


class SqlAlchemyDmcaNoticesRepository(DmcaNoticesRepository):
    """Postgres-backed DMCA notice repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, org_id: UUID, payload: DmcaNoticeCreate) -> DmcaNotice:
        model = DmcaNoticeModel(org_id=org_id, **payload.model_dump())
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return DmcaNotice.model_validate(model)

    async def list_for_org(
        self,
        *,
        org_id: UUID,
        status: DmcaNoticeStatus | None = None,
    ) -> list[DmcaNotice]:
        query = select(DmcaNoticeModel).where(DmcaNoticeModel.org_id == org_id)
        if status is not None:
            query = query.where(DmcaNoticeModel.status == status.value)
        query = query.order_by(DmcaNoticeModel.created_at.desc())
        result = await self._session.execute(query)
        return [DmcaNotice.model_validate(row) for row in result.scalars().all()]

    async def get(self, *, notice_id: UUID, org_id: UUID) -> DmcaNotice | None:
        result = await self._session.execute(
            select(DmcaNoticeModel).where(
                DmcaNoticeModel.id == notice_id,
                DmcaNoticeModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return DmcaNotice.model_validate(model)

    async def update(
        self,
        *,
        notice_id: UUID,
        org_id: UUID,
        payload: DmcaNoticeUpdateRequest,
    ) -> DmcaNotice | None:
        result = await self._session.execute(
            select(DmcaNoticeModel).where(
                DmcaNoticeModel.id == notice_id,
                DmcaNoticeModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if "status" in update_data and update_data["status"] is not None:
            status = update_data["status"]
            model.status = status.value
            if status in (DmcaNoticeStatus.CONTENT_REMOVED, DmcaNoticeStatus.RESOLVED):
                model.resolved_at = model.resolved_at or datetime.utcnow()
            elif status in (DmcaNoticeStatus.RECEIVED, DmcaNoticeStatus.UNDER_REVIEW):
                model.resolved_at = None
        if "action_taken" in update_data:
            model.action_taken = update_data["action_taken"]
        if "reviewer_notes" in update_data:
            model.reviewer_notes = update_data["reviewer_notes"]
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return DmcaNotice.model_validate(model)
