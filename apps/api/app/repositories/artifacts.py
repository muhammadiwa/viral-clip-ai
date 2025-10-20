from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.artifacts import Artifact, ArtifactCreate
from ..models.artifact import ArtifactModel


class ArtifactsRepository(Protocol):
    async def create(self, *, org_id: UUID, payload: ArtifactCreate) -> Artifact:
        ...

    async def list_for_project(self, *, project_id: UUID, org_id: UUID) -> list[Artifact]:
        ...

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Artifact]:
        ...

    async def list_for_clip(self, *, clip_id: UUID, org_id: UUID) -> list[Artifact]:
        ...


class InMemoryArtifactsRepository:
    """Simple in-memory artifact persistence for early iterations."""

    def __init__(self) -> None:
        self._artifacts: dict[UUID, Artifact] = {}

    async def create(self, *, org_id: UUID, payload: ArtifactCreate) -> Artifact:
        now = datetime.utcnow()
        artifact = Artifact(
            org_id=org_id,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    async def list_for_project(self, *, project_id: UUID, org_id: UUID) -> list[Artifact]:
        return [
            artifact
            for artifact in self._artifacts.values()
            if artifact.org_id == org_id and artifact.project_id == project_id
        ]

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Artifact]:
        return [
            artifact
            for artifact in self._artifacts.values()
            if artifact.org_id == org_id and artifact.video_id == video_id
        ]

    async def list_for_clip(self, *, clip_id: UUID, org_id: UUID) -> list[Artifact]:
        return [
            artifact
            for artifact in self._artifacts.values()
            if artifact.org_id == org_id and artifact.clip_id == clip_id
        ]


class SqlAlchemyArtifactsRepository:
    """SQL-backed artifact repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, org_id: UUID, payload: ArtifactCreate) -> Artifact:
        now = datetime.utcnow()
        model = ArtifactModel(
            org_id=org_id,
            project_id=payload.project_id,
            video_id=payload.video_id,
            clip_id=payload.clip_id,
            retell_id=payload.retell_id,
            kind=payload.kind.value,
            uri=payload.uri,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return Artifact.model_validate(model)

    async def list_for_project(self, *, project_id: UUID, org_id: UUID) -> list[Artifact]:
        result = await self._session.execute(
            select(ArtifactModel)
            .where(
                ArtifactModel.project_id == project_id,
                ArtifactModel.org_id == org_id,
            )
            .order_by(ArtifactModel.created_at.desc())
        )
        return [Artifact.model_validate(row) for row in result.scalars().all()]

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Artifact]:
        result = await self._session.execute(
            select(ArtifactModel)
            .where(
                ArtifactModel.video_id == video_id,
                ArtifactModel.org_id == org_id,
            )
            .order_by(ArtifactModel.created_at.desc())
        )
        return [Artifact.model_validate(row) for row in result.scalars().all()]

    async def list_for_clip(self, *, clip_id: UUID, org_id: UUID) -> list[Artifact]:
        result = await self._session.execute(
            select(ArtifactModel)
            .where(
                ArtifactModel.clip_id == clip_id,
                ArtifactModel.org_id == org_id,
            )
            .order_by(ArtifactModel.created_at.desc())
        )
        return [Artifact.model_validate(row) for row in result.scalars().all()]
