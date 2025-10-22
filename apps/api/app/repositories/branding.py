"""Repository helpers for brand kit persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..domain.branding import (
    BrandAsset,
    BrandAssetCreate,
    BrandKit,
    BrandKitCreate,
    BrandKitUpdate,
)
from ..models.branding import BrandAssetModel, BrandKitModel


class BrandKitRepository(Protocol):
    async def create(self, org_id: UUID, payload: BrandKitCreate) -> BrandKit: ...

    async def list(self, org_id: UUID, *, include_archived: bool = False) -> list[BrandKit]: ...

    async def get(self, org_id: UUID, brand_kit_id: UUID) -> BrandKit | None: ...

    async def update(
        self, org_id: UUID, brand_kit_id: UUID, payload: BrandKitUpdate
    ) -> BrandKit | None: ...

    async def create_asset(
        self, org_id: UUID, brand_kit_id: UUID, payload: BrandAssetCreate
    ) -> BrandAsset: ...

    async def list_assets(self, org_id: UUID, brand_kit_id: UUID) -> list[BrandAsset]: ...

    async def delete_asset(
        self, org_id: UUID, brand_kit_id: UUID, asset_id: UUID
    ) -> None: ...


class SqlAlchemyBrandKitRepository(BrandKitRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: UUID, payload: BrandKitCreate) -> BrandKit:
        model = BrandKitModel(org_id=org_id, **payload.model_dump())
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(model)
        return self._build_brand_kit(model)

    async def list(
        self, org_id: UUID, *, include_archived: bool = False
    ) -> list[BrandKit]:
        query = select(BrandKitModel).where(BrandKitModel.org_id == org_id)
        if not include_archived:
            query = query.where(BrandKitModel.is_archived.is_(False))
        query = query.options(selectinload(BrandKitModel.assets)).order_by(
            BrandKitModel.created_at.desc()
        )
        result = await self._session.execute(query)
        return [self._build_brand_kit(row) for row in result.scalars().all()]

    async def get(self, org_id: UUID, brand_kit_id: UUID) -> BrandKit | None:
        result = await self._session.execute(
            select(BrandKitModel)
            .where(
                BrandKitModel.id == brand_kit_id,
                BrandKitModel.org_id == org_id,
            )
            .options(selectinload(BrandKitModel.assets))
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._build_brand_kit(model)

    async def update(
        self, org_id: UUID, brand_kit_id: UUID, payload: BrandKitUpdate
    ) -> BrandKit | None:
        result = await self._session.execute(
            select(BrandKitModel)
            .where(
                BrandKitModel.id == brand_kit_id,
                BrandKitModel.org_id == org_id,
            )
            .options(selectinload(BrandKitModel.assets))
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(model, key, value)
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return self._build_brand_kit(model)

    async def create_asset(
        self, org_id: UUID, brand_kit_id: UUID, payload: BrandAssetCreate
    ) -> BrandAsset:
        model = BrandAssetModel(
            org_id=org_id,
            brand_kit_id=brand_kit_id,
            **payload.model_dump(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(model)
        return BrandAsset.model_validate(model)

    async def list_assets(self, org_id: UUID, brand_kit_id: UUID) -> list[BrandAsset]:
        stmt = select(BrandAssetModel).where(
            BrandAssetModel.org_id == org_id,
            BrandAssetModel.brand_kit_id == brand_kit_id,
        )
        result = await self._session.execute(stmt)
        return [BrandAsset.model_validate(row) for row in result.scalars().all()]

    async def delete_asset(
        self, org_id: UUID, brand_kit_id: UUID, asset_id: UUID
    ) -> None:
        stmt = (
            delete(BrandAssetModel)
            .where(
                BrandAssetModel.org_id == org_id,
                BrandAssetModel.brand_kit_id == brand_kit_id,
                BrandAssetModel.id == asset_id,
            )
            .execution_options(synchronize_session="fetch")
        )
        await self._session.execute(stmt)
        await self._session.commit()

    def _build_brand_kit(self, model: BrandKitModel) -> BrandKit:
        brand_kit = BrandKit.model_validate(model)
        brand_kit.assets = [BrandAsset.model_validate(asset) for asset in model.assets]
        return brand_kit
