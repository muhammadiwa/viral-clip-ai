from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.jobs import JobCreate, JobType
from ...domain.organizations import MembershipRole
from ...domain.retells import (
    RetellCreateRequest,
    RetellResponse,
    RetellStatus,
    RetellUpdateRequest,
)
from ...repositories.jobs import JobsRepository
from ...repositories.projects import ProjectsRepository
from ...repositories.retells import RetellsRepository
from ..dependencies import (
    get_active_membership,
    get_jobs_repository,
    get_projects_repository,
    get_retells_repository,
    get_org_id,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_task_dispatcher,
)
from ...services.tasks import TaskDispatcher

router = APIRouter(prefix="/projects/{project_id}/retell", tags=["retell"])


@router.post(
    "",
    response_model=RetellResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(
            require_org_role(
                MembershipRole.OWNER,
                MembershipRole.ADMIN,
                MembershipRole.EDITOR,
            )
        )
    ],
)
async def request_movie_retell(
    project_id: UUID,
    payload: RetellCreateRequest | None = None,
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("projects:retell")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> RetellResponse:
    cached = idempotency.get_response(RetellResponse)
    if cached:
        return cached
    project = await projects_repo.get(project_id, org_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    existing = await retells_repo.get_latest_for_project(project_id=project.id, org_id=org_id)
    if existing and existing.status in {RetellStatus.QUEUED, RetellStatus.GENERATING}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie retell generation already in progress",
        )

    request_payload = payload or RetellCreateRequest()
    retell_id = uuid4()
    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=project.id,
            job_type=JobType.MOVIE_RETELL,
            retell_id=retell_id,
        ),
    )

    retell = await retells_repo.create(
        retell_id=retell_id,
        org_id=org_id,
        project_id=project.id,
        job_id=job.id,
        payload=request_payload,
    )

    response = RetellResponse(data=retell)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    tasks.enqueue_retell(job_id=job.id, org_id=org_id)
    return response


@router.get(
    "",
    response_model=RetellResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_movie_retell(
    project_id: UUID,
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    org_id: UUID = Depends(get_org_id),
) -> RetellResponse:
    retell = await retells_repo.get_latest_for_project(project_id=project_id, org_id=org_id)
    if not retell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retell not found")

    return RetellResponse(data=retell)


@router.patch(
    "/{retell_id}",
    response_model=RetellResponse,
    dependencies=[
        Depends(
            require_org_role(
                MembershipRole.OWNER,
                MembershipRole.ADMIN,
                MembershipRole.EDITOR,
            )
        )
    ],
)
async def update_movie_retell_details(
    project_id: UUID,
    retell_id: UUID,
    payload: RetellUpdateRequest,
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    org_id: UUID = Depends(get_org_id),
) -> RetellResponse:
    retell = await retells_repo.get(retell_id=retell_id, org_id=org_id)
    if not retell or retell.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retell not found")

    updated = await retells_repo.update_details(
        retell_id=retell_id,
        org_id=org_id,
        payload=payload,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retell not found")

    return RetellResponse(data=updated)
