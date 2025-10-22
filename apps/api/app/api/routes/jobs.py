from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder

from ...domain.audit import AuditLogCreate
from ...domain.clips import ClipStyleStatus, ClipVoiceStatus
from ...domain.jobs import (
    Job,
    JobControlRequest,
    JobListResponse,
    JobResponse,
    JobStatus,
    JobType,
    JobUpdateRequest,
)
from ...domain.organizations import Membership, MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.projects import ProjectExportStatus
from ...domain.retells import RetellStatus
from ...domain.transcripts import AlignmentStatus, TranscriptStatus
from ...domain.videos import VideoStatus
from ...domain.users import User
from ...domain.webhooks import WebhookEventType
from ...repositories.audit import AuditLogsRepository
from ...repositories.clips import ClipsRepository
from ...repositories.jobs import JobsRepository
from ...repositories.projects import ProjectsRepository
from ...repositories.retells import RetellsRepository
from ...repositories.transcripts import TranscriptsRepository
from ...repositories.videos import VideosRepository
from ...repositories.webhooks import WebhookEndpointsRepository
from ...services.job_events import JobEventBroker
from ...services.pagination import paginate_sequence
from ..dependencies import (
    ensure_websocket_membership,
    get_active_membership,
    get_audit_logs_repository,
    get_clips_repository,
    get_current_user,
    get_jobs_repository,
    get_projects_repository,
    get_retells_repository,
    get_transcripts_repository,
    get_org_id,
    get_videos_repository,
    get_job_event_broker,
    get_webhook_endpoints_repository,
    require_org_role,
    require_worker_token,
    enforce_rate_limit,
    get_pagination_params,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_job(
    job_id: UUID,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
) -> JobResponse:
    job = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobResponse(data=job)


@router.websocket("/{job_id}/events")
async def stream_job_events(
    websocket: WebSocket,
    job_id: UUID,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
):
    try:
        org_id, _ = await ensure_websocket_membership(websocket)
    except HTTPException:
        return

    job = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not job:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Job not found")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "event": "snapshot",
            "data": jsonable_encoder(job, exclude_none=True),
        }
    )

    try:
        async for update in events_broker.subscribe(job_id):
            if update.org_id != org_id:
                continue
            await websocket.send_json(
                {
                    "event": "update",
                    "data": jsonable_encoder(update, exclude_none=True),
                }
            )
    except WebSocketDisconnect:
        return


@router.get(
    "/projects/{project_id}",
    response_model=JobListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_jobs_for_project(
    project_id: UUID,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> JobListResponse:
    jobs = await jobs_repo.list_for_project(project_id=project_id, org_id=org_id)
    paginated, meta = paginate_sequence(jobs, pagination)
    return JobListResponse(data=paginated, count=meta.count, pagination=meta)


@router.patch(
    "/{job_id}",
    response_model=JobResponse,
    dependencies=[
        Depends(require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN))
    ],
)
async def update_job(
    job_id: UUID,
    payload: JobUpdateRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> JobResponse:
    job = await _update_job_status(
        job_id=job_id,
        org_id=org_id,
        payload=payload,
        jobs_repo=jobs_repo,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    return JobResponse(data=job)


@router.patch(
    "/{job_id}/worker-status",
    response_model=JobResponse,
    dependencies=[Depends(require_worker_token)],
)
async def worker_update_job(
    job_id: UUID,
    payload: JobUpdateRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
) -> JobResponse:
    job = await _update_job_status(
        job_id=job_id,
        org_id=org_id,
        payload=payload,
        jobs_repo=jobs_repo,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    return JobResponse(data=job)


async def _update_job_status(
    *,
    job_id: UUID,
    org_id: UUID,
    payload: JobUpdateRequest,
    jobs_repo: JobsRepository,
    videos_repo: VideosRepository,
    clips_repo: ClipsRepository,
    projects_repo: ProjectsRepository,
    retells_repo: RetellsRepository,
    transcripts_repo: TranscriptsRepository,
    events_broker: JobEventBroker,
    webhooks_repo: WebhookEndpointsRepository,
) -> Job:
    existing = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job = await jobs_repo.update_status(
        job_id=job_id,
        org_id=org_id,
        status=payload.status,
        progress=payload.progress,
        message=payload.message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    await _propagate_job_side_effects(
        job,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        org_id=org_id,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    return job


@router.post(
    "/{job_id}:cancel",
    response_model=JobResponse,
)
async def cancel_job(
    job_id: UUID,
    payload: JobControlRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    _: object = Depends(enforce_rate_limit("jobs:control")),
) -> JobResponse:
    existing = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if existing.status in {JobStatus.SUCCEEDED, JobStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job can no longer be cancelled",
        )

    job = await jobs_repo.update_status(
        job_id=job_id,
        org_id=org_id,
        status=JobStatus.CANCELLED,
        message=payload.message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    await _propagate_job_side_effects(
        job,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        org_id=org_id,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="job.cancelled",
            target_type="job",
            target_id=job.id,
            target_display_name=job.job_type.value,
            message=payload.message,
            metadata={
                "job_type": job.job_type.value,
                "status": job.status.value,
            },
        ),
    )

    return JobResponse(data=job)


@router.post(
    "/{job_id}:pause",
    response_model=JobResponse,
)
async def pause_job(
    job_id: UUID,
    payload: JobControlRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    _: object = Depends(enforce_rate_limit("jobs:control")),
) -> JobResponse:
    existing = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if existing.status != JobStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only running jobs can be paused",
        )

    job = await jobs_repo.update_status(
        job_id=job_id,
        org_id=org_id,
        status=JobStatus.PAUSED,
        progress=existing.progress,
        message=payload.message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    await _propagate_job_side_effects(
        job,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        org_id=org_id,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="job.paused",
            target_type="job",
            target_id=job.id,
            target_display_name=job.job_type.value,
            message=payload.message,
            metadata={
                "job_type": job.job_type.value,
                "status": job.status.value,
            },
        ),
    )

    return JobResponse(data=job)


@router.post(
    "/{job_id}:resume",
    response_model=JobResponse,
)
async def resume_job(
    job_id: UUID,
    payload: JobControlRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    _: object = Depends(enforce_rate_limit("jobs:control")),
) -> JobResponse:
    existing = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if existing.status != JobStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only paused jobs can be resumed",
        )

    job = await jobs_repo.update_status(
        job_id=job_id,
        org_id=org_id,
        status=JobStatus.QUEUED,
        progress=existing.progress,
        message=payload.message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    await _propagate_job_side_effects(
        job,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        org_id=org_id,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="job.resumed",
            target_type="job",
            target_id=job.id,
            target_display_name=job.job_type.value,
            message=payload.message,
            metadata={
                "job_type": job.job_type.value,
                "status": job.status.value,
            },
        ),
    )

    return JobResponse(data=job)


@router.post(
    "/{job_id}:retry",
    response_model=JobResponse,
)
async def retry_job(
    job_id: UUID,
    payload: JobControlRequest,
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    projects_repo: ProjectsRepository = Depends(get_projects_repository),
    retells_repo: RetellsRepository = Depends(get_retells_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    org_id: UUID = Depends(get_org_id),
    events_broker: JobEventBroker = Depends(get_job_event_broker),
    webhooks_repo: WebhookEndpointsRepository = Depends(
        get_webhook_endpoints_repository
    ),
    audit_repo: AuditLogsRepository = Depends(get_audit_logs_repository),
    membership: Membership = Depends(
        require_org_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    current_user: User = Depends(get_current_user),
    _: object = Depends(enforce_rate_limit("jobs:control")),
) -> JobResponse:
    existing = await jobs_repo.get(job_id=job_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if existing.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or cancelled jobs can be retried",
        )

    job = await jobs_repo.reset_for_retry(
        job_id=job_id,
        org_id=org_id,
        message=payload.message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    await _propagate_job_side_effects(
        job,
        videos_repo=videos_repo,
        clips_repo=clips_repo,
        projects_repo=projects_repo,
        retells_repo=retells_repo,
        transcripts_repo=transcripts_repo,
        org_id=org_id,
        events_broker=events_broker,
        webhooks_repo=webhooks_repo,
    )

    await audit_repo.record(
        org_id=org_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=membership.role,
        payload=AuditLogCreate(
            action="job.retried",
            target_type="job",
            target_id=job.id,
            target_display_name=job.job_type.value,
            message=payload.message,
            metadata={
                "job_type": job.job_type.value,
                "status": job.status.value,
                "retry_count": job.retry_count,
            },
        ),
    )

    return JobResponse(data=job)


async def _propagate_job_side_effects(
    job: Job,
    *,
    videos_repo: VideosRepository,
    clips_repo: ClipsRepository,
    projects_repo: ProjectsRepository,
    retells_repo: RetellsRepository,
    transcripts_repo: TranscriptsRepository,
    org_id: UUID,
    events_broker: JobEventBroker,
    webhooks_repo: WebhookEndpointsRepository,
) -> None:
    if job.video_id:
        video_status = _derive_video_status(job_type=job.job_type, status=job.status)
        if video_status is not None:
            await videos_repo.update_status(
                video_id=job.video_id,
                org_id=org_id,
                status=video_status,
            )

    styled_clip = None
    voiced_clip = None
    exported_project = None

    if job.clip_id:
        if job.job_type == JobType.SUBTITLE_RENDER:
            clip_status = _derive_clip_style_status(status=job.status)
            if clip_status is not None:
                styled_clip = await clips_repo.update_style_status(
                    clip_id=job.clip_id,
                    org_id=org_id,
                    status=clip_status,
                    error=_error_message_for_status(job.status, job.message),
                )
        elif job.job_type == JobType.TTS_RENDER:
            voice_status = _derive_clip_voice_status(status=job.status)
            if voice_status is not None:
                voiced_clip = await clips_repo.update_voice_status(
                    clip_id=job.clip_id,
                    org_id=org_id,
                    status=voice_status,
                    error=_error_message_for_status(job.status, job.message),
                )

    if job.job_type == JobType.PROJECT_EXPORT:
        export_status = _derive_project_export_status(status=job.status)
        if export_status is not None:
            exported_project = await projects_repo.update_export_status(
                project_id=job.project_id,
                org_id=org_id,
                status=export_status,
                error=_error_message_for_status(job.status, job.message),
            )

    if job.retell_id:
        retell_status = _derive_retell_status(status=job.status)
        if retell_status is not None:
            await retells_repo.update_status(
                retell_id=job.retell_id,
                org_id=org_id,
                status=retell_status,
                message=job.message,
                error=_error_message_for_status(job.status, job.message),
            )

    if job.transcript_id:
        if job.job_type == JobType.TRANSCRIPTION:
            transcript_status = _derive_transcript_status(status=job.status)
            if transcript_status is not None:
                await transcripts_repo.update_transcription(
                    transcript_id=job.transcript_id,
                    org_id=org_id,
                    status=transcript_status,
                    error=_error_message_for_status(job.status, job.message),
                )
        elif job.job_type == JobType.ALIGNMENT:
            alignment_status = _derive_alignment_status(status=job.status)
            if alignment_status is not None:
                await transcripts_repo.update_alignment(
                    transcript_id=job.transcript_id,
                    org_id=org_id,
                    status=alignment_status,
                    error=_error_message_for_status(job.status, job.message),
                )

    await events_broker.publish(job)
    await webhooks_repo.publish_event(
        org_id=org_id,
        event_type=WebhookEventType.JOB_UPDATED,
        payload={"job": jsonable_encoder(job, exclude_none=True)},
    )

    if styled_clip and job.status == JobStatus.SUCCEEDED:
        await webhooks_repo.publish_event(
            org_id=org_id,
            event_type=WebhookEventType.CLIP_STYLED,
            payload={
                "job_id": str(job.id),
                "clip": jsonable_encoder(styled_clip, exclude_none=True),
            },
        )

    if voiced_clip and job.status == JobStatus.SUCCEEDED:
        await webhooks_repo.publish_event(
            org_id=org_id,
            event_type=WebhookEventType.CLIP_TTS_COMPLETED,
            payload={
                "job_id": str(job.id),
                "clip": jsonable_encoder(voiced_clip, exclude_none=True),
            },
        )

    if exported_project and job.status == JobStatus.SUCCEEDED:
        await webhooks_repo.publish_event(
            org_id=org_id,
            event_type=WebhookEventType.PROJECT_EXPORTED,
            payload={
                "job_id": str(job.id),
                "project": jsonable_encoder(
                    exported_project, exclude_none=True
                ),
            },
        )


def _error_message_for_status(status: JobStatus, message: str | None) -> str | None:
    if status in {JobStatus.FAILED, JobStatus.CANCELLED}:
        return message
    return None


def _derive_video_status(*, job_type: JobType, status: JobStatus) -> VideoStatus | None:
    if job_type == JobType.INGEST:
        if status == JobStatus.RUNNING:
            return VideoStatus.INGESTING
        if status == JobStatus.SUCCEEDED:
            return VideoStatus.READY_FOR_TRANSCODE
        if status == JobStatus.FAILED:
            return VideoStatus.INGEST_FAILED
        if status == JobStatus.CANCELLED:
            return VideoStatus.INGEST_FAILED
    if job_type == JobType.TRANSCODE:
        if status == JobStatus.RUNNING:
            return VideoStatus.TRANSCODING
        if status == JobStatus.SUCCEEDED:
            return VideoStatus.READY_FOR_TRANSCRIPTION
        if status == JobStatus.FAILED:
            return VideoStatus.TRANSCODE_FAILED
        if status == JobStatus.CANCELLED:
            return VideoStatus.TRANSCODE_FAILED
    if job_type == JobType.TRANSCRIPTION:
        if status == JobStatus.RUNNING:
            return VideoStatus.TRANSCRIBING
        if status == JobStatus.SUCCEEDED:
            return VideoStatus.READY_FOR_ALIGNMENT
        if status == JobStatus.FAILED:
            return VideoStatus.TRANSCRIPTION_FAILED
        if status == JobStatus.CANCELLED:
            return VideoStatus.TRANSCRIPTION_FAILED
    if job_type == JobType.ALIGNMENT:
        if status == JobStatus.RUNNING:
            return VideoStatus.ALIGNING
        if status == JobStatus.SUCCEEDED:
            return VideoStatus.READY_FOR_ANALYSIS
        if status == JobStatus.FAILED:
            return VideoStatus.ALIGNMENT_FAILED
        if status == JobStatus.CANCELLED:
            return VideoStatus.ALIGNMENT_FAILED
    if job_type == JobType.CLIP_DISCOVERY:
        if status == JobStatus.RUNNING:
            return VideoStatus.ANALYZING
        if status == JobStatus.SUCCEEDED:
            return VideoStatus.READY_FOR_CLIP_REVIEW
        if status == JobStatus.FAILED:
            return VideoStatus.ANALYSIS_FAILED
        if status == JobStatus.CANCELLED:
            return VideoStatus.ANALYSIS_FAILED
    if job_type == JobType.SUBTITLE_RENDER:
        return None
    if job_type == JobType.TTS_RENDER:
        return None
    if job_type == JobType.PROJECT_EXPORT:
        return None
    if job_type == JobType.MOVIE_RETELL:
        return None
    return None


def _derive_clip_style_status(*, status: JobStatus) -> ClipStyleStatus | None:
    if status == JobStatus.RUNNING:
        return ClipStyleStatus.STYLING
    if status == JobStatus.SUCCEEDED:
        return ClipStyleStatus.STYLED
    if status == JobStatus.FAILED:
        return ClipStyleStatus.STYLE_FAILED
    if status == JobStatus.CANCELLED:
        return ClipStyleStatus.STYLE_FAILED
    return None


def _derive_clip_voice_status(*, status: JobStatus) -> ClipVoiceStatus | None:
    if status == JobStatus.RUNNING:
        return ClipVoiceStatus.SYNTHESIZING
    if status == JobStatus.SUCCEEDED:
        return ClipVoiceStatus.SYNTHESIZED
    if status == JobStatus.FAILED:
        return ClipVoiceStatus.VOICE_FAILED
    if status == JobStatus.CANCELLED:
        return ClipVoiceStatus.VOICE_FAILED
    return None


def _derive_project_export_status(
    *, status: JobStatus
) -> ProjectExportStatus | None:
    if status == JobStatus.RUNNING:
        return ProjectExportStatus.EXPORTING
    if status == JobStatus.SUCCEEDED:
        return ProjectExportStatus.EXPORTED
    if status == JobStatus.FAILED:
        return ProjectExportStatus.EXPORT_FAILED
    if status == JobStatus.CANCELLED:
        return ProjectExportStatus.EXPORT_FAILED
    return None


def _derive_retell_status(*, status: JobStatus) -> RetellStatus | None:
    if status == JobStatus.RUNNING:
        return RetellStatus.GENERATING
    if status == JobStatus.SUCCEEDED:
        return RetellStatus.READY
    if status == JobStatus.FAILED:
        return RetellStatus.FAILED
    if status == JobStatus.QUEUED:
        return RetellStatus.QUEUED
    if status == JobStatus.CANCELLED:
        return RetellStatus.FAILED
    return None


def _derive_transcript_status(*, status: JobStatus) -> TranscriptStatus | None:
    if status == JobStatus.RUNNING:
        return TranscriptStatus.TRANSCRIBING
    if status == JobStatus.SUCCEEDED:
        return TranscriptStatus.COMPLETED
    if status == JobStatus.FAILED:
        return TranscriptStatus.FAILED
    if status == JobStatus.QUEUED:
        return TranscriptStatus.QUEUED
    if status == JobStatus.CANCELLED:
        return TranscriptStatus.FAILED
    return None


def _derive_alignment_status(*, status: JobStatus) -> AlignmentStatus | None:
    if status == JobStatus.RUNNING:
        return AlignmentStatus.ALIGNING
    if status == JobStatus.SUCCEEDED:
        return AlignmentStatus.ALIGNED
    if status == JobStatus.FAILED:
        return AlignmentStatus.FAILED
    if status == JobStatus.QUEUED:
        return AlignmentStatus.QUEUED
    if status == JobStatus.CANCELLED:
        return AlignmentStatus.FAILED
    return None
