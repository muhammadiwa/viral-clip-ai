from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.jobs import JobCreate, JobType
from ...domain.organizations import MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.projects import (
    ProjectCreate,
    ProjectExportRequest,
    ProjectExportResponse,
    ProjectExportStatus,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from ...repositories.jobs import JobsRepository
from ...repositories.projects import ProjectsRepository
from ...repositories.branding import BrandKitRepository
from ...services.pagination import paginate_sequence
from ...services.tasks import TaskDispatcher
from ..dependencies import (
    get_active_membership,
    get_brand_kit_repository,
    get_jobs_repository,
    get_org_id,
    get_projects_repository,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
    get_task_dispatcher,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
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
async def create_project(
    payload: ProjectCreate,
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    brand_repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> ProjectResponse:
    cached = idempotency.get_response(ProjectResponse)
    if cached:
        return cached
    if payload.brand_kit_id is not None:
        brand_kit = await brand_repo.get(org_id, payload.brand_kit_id)
        if brand_kit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Brand kit not found",
            )
    project = await projects_repo.create(org_id=org_id, payload=payload)
    response = ProjectResponse(data=project)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "",
    response_model=ProjectListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_projects(
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> ProjectListResponse:
    projects = await projects_repo.list_for_org(org_id)
    paginated, meta = paginate_sequence(projects, pagination)
    return ProjectListResponse(data=paginated, count=meta.count, pagination=meta)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
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
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    brand_repo: BrandKitRepository = Depends(get_brand_kit_repository),
    org_id: UUID = Depends(get_org_id),
) -> ProjectResponse:
    if payload.brand_kit_id is not None:
        brand_kit = await brand_repo.get(org_id, payload.brand_kit_id)
        if brand_kit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Brand kit not found",
            )
    project = await projects_repo.update(
        project_id=project_id, org_id=org_id, payload=payload
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse(data=project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_project(
    project_id: UUID,
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    org_id: UUID = Depends(get_org_id),
) -> ProjectResponse:
    project = await projects_repo.get(project_id, org_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse(data=project)


@router.post(
    "/{project_id}/export",
    response_model=ProjectExportResponse,
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
async def request_project_export(
    project_id: UUID,
    payload: ProjectExportRequest | None = None,
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("projects:export")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> ProjectExportResponse:
    cached = idempotency.get_response(ProjectExportResponse)
    if cached:
        return cached
    project = await projects_repo.get(project_id, org_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.export_status in {
        ProjectExportStatus.EXPORT_QUEUED,
        ProjectExportStatus.EXPORTING,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project export already in progress",
        )

    request_payload = payload or ProjectExportRequest()
    updated_project = await projects_repo.update_export_request(
        project_id=project.id,
        org_id=org_id,
        payload=request_payload,
    )
    if not updated_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=project.id,
            job_type=JobType.PROJECT_EXPORT,
        ),
    )

    response = ProjectExportResponse(
        job_id=job.id,
        project_id=project.id,
        export_status=updated_project.export_status,
        format=request_payload.format,
        resolution=request_payload.resolution,
        include_subtitles=request_payload.include_subtitles,
        include_voice_over=request_payload.include_voice_over,
    )
    await idempotency.store_response(
        response,
        status_code=status.HTTP_202_ACCEPTED,
    )
    tasks.enqueue_project_export(job_id=job.id, org_id=org_id)
    return response
