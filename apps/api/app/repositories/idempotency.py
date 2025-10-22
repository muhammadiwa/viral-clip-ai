from __future__ import annotations

from typing import Dict, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.idempotency import IdempotencyRecord
from ..models.idempotency import IdempotencyRecordModel


class IdempotencyRepository:
    async def get(self, org_id: UUID, key: str) -> IdempotencyRecord | None:
        raise NotImplementedError

    async def save(self, record: IdempotencyRecord) -> IdempotencyRecord:
        raise NotImplementedError


class InMemoryIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self._records: Dict[Tuple[UUID, str], IdempotencyRecord] = {}

    async def get(self, org_id: UUID, key: str) -> IdempotencyRecord | None:
        return self._records.get((org_id, key))

    async def save(self, record: IdempotencyRecord) -> IdempotencyRecord:
        self._records[(record.org_id, record.key)] = record
        return record


class SqlAlchemyIdempotencyRepository(IdempotencyRepository):
    """Persists idempotent responses to Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, org_id: UUID, key: str) -> IdempotencyRecord | None:
        result = await self._session.execute(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.org_id == org_id,
                IdempotencyRecordModel.key == key,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return IdempotencyRecord.model_validate(model)

    async def save(self, record: IdempotencyRecord) -> IdempotencyRecord:
        result = await self._session.execute(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.org_id == record.org_id,
                IdempotencyRecordModel.key == record.key,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = IdempotencyRecordModel(
                id=record.id,
                org_id=record.org_id,
                key=record.key,
                method=record.method,
                path=record.path,
                status_code=record.status_code,
                payload=record.payload,
            )
            self._session.add(model)
        else:
            model.method = record.method
            model.path = record.path
            model.status_code = record.status_code
            model.payload = record.payload
        await self._session.commit()
        return IdempotencyRecord.model_validate(model)

