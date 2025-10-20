from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.retells import (
    Retell,
    RetellCreateRequest,
    RetellStatus,
    RetellUpdateRequest,
)
from ..models.retell import RetellModel


class RetellsRepository(Protocol):
    async def create(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        project_id: UUID,
        job_id: UUID,
        payload: RetellCreateRequest,
    ) -> Retell: ...

    async def get(self, retell_id: UUID, org_id: UUID) -> Retell | None: ...

    async def get_latest_for_project(self, project_id: UUID, org_id: UUID) -> Retell | None: ...

    async def update_status(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        status: RetellStatus,
        message: str | None = None,
        error: str | None = None,
    ) -> Retell | None: ...

    async def update_details(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        payload: RetellUpdateRequest,
    ) -> Retell | None: ...


class InMemoryRetellsRepository:
    """Ephemeral storage for movie retell sessions."""

    def __init__(self) -> None:
        self._retells: dict[UUID, Retell] = {}

    async def create(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        project_id: UUID,
        job_id: UUID,
        payload: RetellCreateRequest,
    ) -> Retell:
        retell = Retell(
            id=retell_id,
            org_id=org_id,
            project_id=project_id,
            job_id=job_id,
            **payload.model_dump(),
        )
        self._retells[retell.id] = retell
        return retell

    async def get(self, retell_id: UUID, org_id: UUID) -> Retell | None:
        retell = self._retells.get(retell_id)
        if retell and retell.org_id == org_id:
            return retell
        return None

    async def get_latest_for_project(self, project_id: UUID, org_id: UUID) -> Retell | None:
        retells = [
            retell
            for retell in self._retells.values()
            if retell.org_id == org_id and retell.project_id == project_id
        ]
        if not retells:
            return None
        retells.sort(key=lambda entry: entry.created_at, reverse=True)
        return retells[0]

    async def update_status(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        status: RetellStatus,
        message: str | None = None,
        error: str | None = None,
    ) -> Retell | None:
        retell = await self.get(retell_id, org_id)
        if not retell:
            return None
        update_data: dict[str, object | None] = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }
        if message is not None:
            update_data["status_message"] = message
        if status == RetellStatus.FAILED:
            update_data["error"] = error or message
        else:
            update_data["error"] = None
        updated = retell.model_copy(update=update_data)
        self._retells[retell_id] = updated
        return updated

    async def update_details(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        payload: RetellUpdateRequest,
    ) -> Retell | None:
        retell = await self.get(retell_id, org_id)
        if not retell:
            return None

        update_fields = payload.model_dump(exclude_unset=True)
        if not update_fields:
            return retell

        update_fields["updated_at"] = datetime.utcnow()
        updated = retell.model_copy(update=update_fields)
        self._retells[retell_id] = updated
        return updated


class SqlAlchemyRetellsRepository:
    """Retell repository backed by Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        project_id: UUID,
        job_id: UUID,
        payload: RetellCreateRequest,
    ) -> Retell:
        model = RetellModel(
            id=retell_id,
            org_id=org_id,
            project_id=project_id,
            job_id=job_id,
            status=RetellStatus.QUEUED.value,
            status_message=payload.status_message,
            metadata=payload.metadata,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return Retell.model_validate(model)

    async def _get_model(self, retell_id: UUID, org_id: UUID) -> RetellModel | None:
        result = await self._session.execute(
            select(RetellModel).where(
                RetellModel.id == retell_id,
                RetellModel.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get(self, retell_id: UUID, org_id: UUID) -> Retell | None:
        model = await self._get_model(retell_id, org_id)
        if not model:
            return None
        return Retell.model_validate(model)

    async def get_latest_for_project(
        self, project_id: UUID, org_id: UUID
    ) -> Retell | None:
        result = await self._session.execute(
            select(RetellModel)
            .where(
                RetellModel.project_id == project_id,
                RetellModel.org_id == org_id,
            )
            .order_by(RetellModel.created_at.desc())
        )
        model = result.scalars().first()
        if not model:
            return None
        return Retell.model_validate(model)

    async def update_status(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        status: RetellStatus,
        message: str | None = None,
        error: str | None = None,
    ) -> Retell | None:
        model = await self._get_model(retell_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.status = status.value
        model.status_message = message
        model.updated_at = now
        model.error = error if status == RetellStatus.FAILED else None
        await self._session.commit()
        await self._session.refresh(model)
        return Retell.model_validate(model)

    async def update_details(
        self,
        *,
        retell_id: UUID,
        org_id: UUID,
        payload: RetellUpdateRequest,
    ) -> Retell | None:
        model = await self._get_model(retell_id, org_id)
        if not model:
            return None
        update_fields = payload.model_dump(exclude_unset=True)
        if "outline" in update_fields and update_fields["outline"] is not None:
            update_fields["outline"] = update_fields["outline"]
        for field, value in update_fields.items():
            setattr(model, field, value)
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Retell.model_validate(model)
