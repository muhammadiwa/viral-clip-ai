from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.jobs import JobResponse, JobType, JobCreate
from ...domain.organizations import MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.clips import (
    ClipGenerationRequest,
    ClipGenerationResponse,
    ClipListResponse,
)
from ...domain.videos import (
    VideoIngestRequest,
    VideoIngestResponse,
    VideoListResponse,
    VideoResponse,
    VideoStatus,
    VideoSourceType,
    VideoUploadCredentials,
)
from ...repositories.projects import ProjectsRepository
from ...repositories.videos import VideosRepository
from ...repositories.jobs import JobsRepository
from ...repositories.clips import ClipsRepository
from ...services.pagination import paginate_sequence
from ...services.storage import MinioStorageService
from ...services.tasks import TaskDispatcher
from ..dependencies import (
    get_active_membership,
    get_org_id,
    get_projects_repository,
    get_videos_repository,
    get_jobs_repository,
    get_clips_repository,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
    get_storage_service,
    get_task_dispatcher,
)

router = APIRouter(tags=["videos"])


@router.post(
    "/videos:ingest",
    response_model=VideoIngestResponse,
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
async def ingest_video(
    payload: VideoIngestRequest,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    storage: MinioStorageService = Depends(get_storage_service),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("videos:ingest")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> VideoIngestResponse:
    cached = idempotency.get_response(VideoIngestResponse)
    if cached:
        return cached
    project = await projects_repo.get(project_id=payload.project_id, org_id=org_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found for organization",
        )

    upload_context: VideoUploadCredentials | None = None
    ingest_payload = payload
    if payload.source_type == VideoSourceType.UPLOAD:
        storage.ensure_bucket()
        upload_key = payload.upload_key
        if upload_key is None:
            upload_key = storage.generate_object_key(
                org_id=org_id, project_id=payload.project_id
            )
            ingest_payload = payload.model_copy(update={"upload_key": upload_key})
        upload_url = storage.generate_presigned_put(upload_key)
        upload_context = VideoUploadCredentials(
            object_key=upload_key,
            upload_url=upload_url,
            expires_in=storage.upload_expiry_seconds,
            headers=storage.default_upload_headers(),
        )

    video = await videos_repo.create(org_id=org_id, payload=ingest_payload)
    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=payload.project_id,
            video_id=video.id,
            job_type=JobType.INGEST,
        ),
    )
    tasks.enqueue_ingest(job_id=job.id, org_id=org_id)
    response = VideoIngestResponse(video=video, job=job, upload=upload_context)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.post(
    "/videos/{video_id}:transcode",
    response_model=JobResponse,
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
async def enqueue_transcode(
    video_id: UUID,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("videos:transcode")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> JobResponse:
    cached = idempotency.get_response(JobResponse)
    if cached:
        return cached
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found for organization",
        )

    if video.status not in {
        VideoStatus.READY_FOR_TRANSCODE,
        VideoStatus.TRANSCODE_FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is not ready for transcode",
        )

    await videos_repo.update_status(
        video_id=video.id,
        org_id=org_id,
        status=VideoStatus.TRANSCODE_QUEUED,
    )

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=video.project_id,
            video_id=video.id,
            job_type=JobType.TRANSCODE,
        ),
    )
    tasks.enqueue_transcode(job_id=job.id, org_id=org_id)

    response = JobResponse(data=job)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.post(
    "/videos/{video_id}/generate-clips",
    response_model=ClipGenerationResponse,
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
async def enqueue_clip_generation(
    video_id: UUID,
    payload: ClipGenerationRequest | None = None,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("videos:generate_clips")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> ClipGenerationResponse:
    cached = idempotency.get_response(ClipGenerationResponse)
    if cached:
        return cached
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found for organization",
        )

    if video.status not in {
        VideoStatus.READY_FOR_ANALYSIS,
        VideoStatus.ANALYSIS_FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is not ready for clip discovery",
        )

    await videos_repo.update_status(
        video_id=video.id,
        org_id=org_id,
        status=VideoStatus.ANALYSIS_QUEUED,
    )

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=video.project_id,
            video_id=video.id,
            job_type=JobType.CLIP_DISCOVERY,
        ),
    )

    request_payload = payload or ClipGenerationRequest()
    response = ClipGenerationResponse(
        job_id=job.id,
        video_id=video.id,
        requested_clips=request_payload.max_clips,
        strategy=request_payload.strategy,
    )
    tasks.enqueue_clip_discovery(
        job_id=job.id, org_id=org_id, max_clips=request_payload.max_clips
    )
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.get(
    "/videos/{video_id}",
    response_model=VideoResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_video(
    video_id: UUID,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
) -> VideoResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )
    return VideoResponse(data=video)


@router.get(
    "/projects/{project_id}/videos",
    response_model=VideoListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_videos_for_project(
    project_id: UUID,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> VideoListResponse:
    project = await projects_repo.get(project_id=project_id, org_id=org_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    videos = await videos_repo.list_for_project(project_id=project_id, org_id=org_id)
    paginated, meta = paginate_sequence(videos, pagination)
    return VideoListResponse(data=paginated, count=meta.count, pagination=meta)


@router.get(
    "/videos/{video_id}/clips",
    response_model=ClipListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_clips_for_video(
    video_id: UUID,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> ClipListResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found for organization",
        )

    clips = await clips_repo.list_for_video(video_id=video_id, org_id=org_id)
    paginated, meta = paginate_sequence(clips, pagination)
    return ClipListResponse(data=paginated, count=meta.count, pagination=meta)


