from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.artifacts import (
    ArtifactCreate,
    ArtifactListResponse,
    ArtifactRegisterRequest,
    ArtifactResponse,
)
from ...domain.organizations import MembershipRole
from ...domain.pagination import PaginationParams
from ...repositories.artifacts import ArtifactsRepository
from ...repositories.clips import ClipsRepository
from ...repositories.projects import ProjectsRepository
from ...repositories.videos import VideosRepository
from ...services.pagination import paginate_sequence
from ..dependencies import (
    get_active_membership,
    get_artifacts_repository,
    get_clips_repository,
    get_org_id,
    get_projects_repository,
    get_videos_repository,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
)

router = APIRouter(tags=["artifacts"])


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_project_artifacts(
    project_id: UUID,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> ArtifactListResponse:
    project = await projects_repo.get(project_id=project_id, org_id=org_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    artifacts = await artifacts_repo.list_for_project(project_id=project_id, org_id=org_id)
    paginated, meta = paginate_sequence(artifacts, pagination)
    return ArtifactListResponse(data=paginated, count=meta.count, pagination=meta)


@router.post(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactResponse,
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
async def register_project_artifact(
    project_id: UUID,
    payload: ArtifactRegisterRequest,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("artifacts:project")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> ArtifactResponse:
    cached = idempotency.get_response(ArtifactResponse)
    if cached:
        return cached
    project = await projects_repo.get(project_id=project_id, org_id=org_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    artifact = await artifacts_repo.create(
        org_id=org_id,
        payload=ArtifactCreate(
            project_id=project.id,
            kind=payload.kind,
            uri=payload.uri,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        ),
    )
    response = ArtifactResponse(data=artifact)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/videos/{video_id}/artifacts",
    response_model=ArtifactListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_video_artifacts(
    video_id: UUID,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> ArtifactListResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    artifacts = await artifacts_repo.list_for_video(video_id=video_id, org_id=org_id)
    paginated, meta = paginate_sequence(artifacts, pagination)
    return ArtifactListResponse(data=paginated, count=meta.count, pagination=meta)


@router.post(
    "/videos/{video_id}/artifacts",
    response_model=ArtifactResponse,
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
async def register_video_artifact(
    video_id: UUID,
    payload: ArtifactRegisterRequest,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("artifacts:video")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> ArtifactResponse:
    cached = idempotency.get_response(ArtifactResponse)
    if cached:
        return cached
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    artifact = await artifacts_repo.create(
        org_id=org_id,
        payload=ArtifactCreate(
            project_id=video.project_id,
            video_id=video.id,
            kind=payload.kind,
            uri=payload.uri,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        ),
    )
    response = ArtifactResponse(data=artifact)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response


@router.get(
    "/clips/{clip_id}/artifacts",
    response_model=ArtifactListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_clip_artifacts(
    clip_id: UUID,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> ArtifactListResponse:
    clip = await clips_repo.get(clip_id=clip_id, org_id=org_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    artifacts = await artifacts_repo.list_for_clip(clip_id=clip_id, org_id=org_id)
    paginated, meta = paginate_sequence(artifacts, pagination)
    return ArtifactListResponse(data=paginated, count=meta.count, pagination=meta)


@router.post(
    "/clips/{clip_id}/artifacts",
    response_model=ArtifactResponse,
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
async def register_clip_artifact(
    clip_id: UUID,
    payload: ArtifactRegisterRequest,
    artifacts_repo: ArtifactsRepository = Depends(get_artifacts_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("artifacts:clip")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> ArtifactResponse:
    cached = idempotency.get_response(ArtifactResponse)
    if cached:
        return cached
    clip = await clips_repo.get(clip_id=clip_id, org_id=org_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    artifact = await artifacts_repo.create(
        org_id=org_id,
        payload=ArtifactCreate(
            project_id=clip.project_id,
            video_id=clip.video_id,
            clip_id=clip.id,
            kind=payload.kind,
            uri=payload.uri,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        ),
    )
    response = ArtifactResponse(data=artifact)
    await idempotency.store_response(response, status_code=status.HTTP_201_CREATED)
    return response
