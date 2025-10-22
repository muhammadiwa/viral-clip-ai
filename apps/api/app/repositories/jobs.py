from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.jobs import Job, JobCreate, JobStatus
from ..models.job import JobModel


class JobsRepository(Protocol):
    async def create(self, org_id: UUID, payload: JobCreate) -> Job: ...

    async def get(self, job_id: UUID, org_id: UUID) -> Job | None: ...

    async def list_for_project(self, project_id: UUID, org_id: UUID) -> list[Job]: ...

    async def update_status(
        self,
        job_id: UUID,
        org_id: UUID,
        status: JobStatus,
        progress: float | None = None,
        message: str | None = None,
    ) -> Job | None: ...

    async def reset_for_retry(
        self,
        job_id: UUID,
        org_id: UUID,
        message: str | None = None,
    ) -> Job | None: ...


class InMemoryJobsRepository:
    """Volatile repository to mimic persistence while bootstrapping."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}

    async def create(self, org_id: UUID, payload: JobCreate) -> Job:
        job = Job(org_id=org_id, **payload.model_dump())
        self._jobs[job.id] = job
        return job

    async def get(self, job_id: UUID, org_id: UUID) -> Job | None:
        job = self._jobs.get(job_id)
        if job and job.org_id == org_id:
            return job
        return None

    async def list_for_project(self, project_id: UUID, org_id: UUID) -> list[Job]:
        return [
            job
            for job in self._jobs.values()
            if job.org_id == org_id and job.project_id == project_id
        ]

    async def update_status(
        self,
        job_id: UUID,
        org_id: UUID,
        status: JobStatus,
        progress: float | None = None,
        message: str | None = None,
    ) -> Job | None:
        job = self._jobs.get(job_id)
        if job and job.org_id == org_id:
            update_data: dict[str, object] = {
                "status": status,
                "updated_at": datetime.utcnow(),
            }
            if progress is not None:
                update_data["progress"] = progress
            if message is not None:
                update_data["message"] = message
            updated = job.model_copy(update=update_data)
            self._jobs[job_id] = updated
            return updated
        return None


class SqlAlchemyJobsRepository:
    """SQL-backed job repository implementation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: UUID, payload: JobCreate) -> Job:
        model = JobModel(
            org_id=org_id,
            project_id=payload.project_id,
            video_id=payload.video_id,
            clip_id=payload.clip_id,
            retell_id=payload.retell_id,
            transcript_id=payload.transcript_id,
            job_type=payload.job_type.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return Job.model_validate(model)

    async def get(self, job_id: UUID, org_id: UUID) -> Job | None:
        result = await self._session.execute(
            select(JobModel).where(
                JobModel.id == job_id,
                JobModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Job.model_validate(model)

    async def list_for_project(self, project_id: UUID, org_id: UUID) -> list[Job]:
        result = await self._session.execute(
            select(JobModel)
            .where(
                JobModel.project_id == project_id,
                JobModel.org_id == org_id,
            )
            .order_by(JobModel.created_at.desc())
        )
        return [Job.model_validate(row) for row in result.scalars().all()]

    async def update_status(
        self,
        job_id: UUID,
        org_id: UUID,
        status: JobStatus,
        progress: float | None = None,
        message: str | None = None,
    ) -> Job | None:
        result = await self._session.execute(
            select(JobModel).where(
                JobModel.id == job_id,
                JobModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.status = status.value
        model.updated_at = datetime.utcnow()
        if progress is not None:
            model.progress = float(progress)
        if message is not None:
            model.message = message
        await self._session.commit()
        await self._session.refresh(model)
        return Job.model_validate(model)

    async def reset_for_retry(
        self,
        job_id: UUID,
        org_id: UUID,
        message: str | None = None,
    ) -> Job | None:
        result = await self._session.execute(
            select(JobModel).where(
                JobModel.id == job_id,
                JobModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.status = JobStatus.QUEUED.value
        model.progress = 0.0
        model.retry_count = (model.retry_count or 0) + 1
        model.updated_at = datetime.utcnow()
        model.message = message
        await self._session.commit()
        await self._session.refresh(model)
        return Job.model_validate(model)
