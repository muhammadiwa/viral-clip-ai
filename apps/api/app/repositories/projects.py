from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.projects import (
    Project,
    ProjectCreate,
    ProjectExportRequest,
    ProjectExportStatus,
    ProjectUpdate,
)
from ..models.project import ProjectModel


class ProjectsRepository(Protocol):
    async def create(self, org_id: UUID, payload: ProjectCreate) -> Project: ...

    async def list_for_org(self, org_id: UUID) -> list[Project]: ...

    async def get(self, project_id: UUID, org_id: UUID) -> Project | None: ...

    async def update(
        self, *, project_id: UUID, org_id: UUID, payload: ProjectUpdate
    ) -> Project | None: ...

    async def update_export_request(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        payload: ProjectExportRequest,
    ) -> Project | None:
        ...

    async def update_export_status(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        status: ProjectExportStatus,
        error: str | None = None,
    ) -> Project | None:
        ...


class InMemoryProjectsRepository:
    """Simple in-memory repository for bootstrapping the API."""

    def __init__(self) -> None:
        self._projects: dict[UUID, Project] = {}

    async def create(self, org_id: UUID, payload: ProjectCreate) -> Project:
        data = payload.model_dump()
        if not data.get("brand_overrides"):
            data["brand_overrides"] = None
        project = Project(org_id=org_id, **data)
        self._projects[project.id] = project
        return project

    async def list_for_org(self, org_id: UUID) -> list[Project]:
        return [project for project in self._projects.values() if project.org_id == org_id]

    async def get(self, project_id: UUID, org_id: UUID) -> Project | None:
        project = self._projects.get(project_id)
        if project and project.org_id == org_id:
            return project
        return None

    async def update(
        self, *, project_id: UUID, org_id: UUID, payload: ProjectUpdate
    ) -> Project | None:
        project = await self.get(project_id, org_id)
        if not project:
            return None
        updates = payload.model_dump(exclude_unset=True)
        if "brand_overrides" in updates and not updates["brand_overrides"]:
            updates["brand_overrides"] = None
        updated = project.model_copy(update=updates | {"updated_at": datetime.utcnow()})
        self._projects[project_id] = updated
        return updated

    async def update_export_request(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        payload: ProjectExportRequest,
    ) -> Project | None:
        project = await self.get(project_id, org_id)
        if not project:
            return None
        settings = payload.model_dump()
        updated = project.model_copy(
            update={
                "export_status": ProjectExportStatus.EXPORT_QUEUED,
                "export_settings": settings,
                "export_error": None,
                "updated_at": datetime.utcnow(),
            }
        )
        self._projects[project_id] = updated
        return updated


class SqlAlchemyProjectsRepository:
    """Projects repository backed by Postgres via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: UUID, payload: ProjectCreate) -> Project:
        data = payload.model_dump()
        if not data.get("brand_overrides"):
            data["brand_overrides"] = None
        model = ProjectModel(org_id=org_id, **data)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return Project.model_validate(model)

    async def list_for_org(self, org_id: UUID) -> list[Project]:
        result = await self._session.execute(
            select(ProjectModel)
                .where(ProjectModel.org_id == org_id)
                .order_by(ProjectModel.created_at.desc())
        )
        return [Project.model_validate(row) for row in result.scalars().all()]

    async def get(self, project_id: UUID, org_id: UUID) -> Project | None:
        result = await self._session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Project.model_validate(model)

    async def update(
        self, *, project_id: UUID, org_id: UUID, payload: ProjectUpdate
    ) -> Project | None:
        result = await self._session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        updates = payload.model_dump(exclude_unset=True)
        if "brand_overrides" in updates and not updates["brand_overrides"]:
            updates["brand_overrides"] = None
        for key, value in updates.items():
            setattr(model, key, value)
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Project.model_validate(model)

    async def update_export_request(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        payload: ProjectExportRequest,
    ) -> Project | None:
        result = await self._session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.export_settings = payload.model_dump()
        model.export_status = ProjectExportStatus.EXPORT_QUEUED.value
        model.export_error = None
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Project.model_validate(model)

    async def update_export_status(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        status: ProjectExportStatus,
        error: str | None = None,
    ) -> Project | None:
        result = await self._session.execute(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.export_status = status.value
        model.updated_at = datetime.utcnow()
        model.export_error = error
        if status == ProjectExportStatus.EXPORTED:
            model.last_exported_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Project.model_validate(model)
