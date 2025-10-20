from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.clips import (
    ClipResponse,
    ClipUpdateRequest,
    ClipVoiceRequest,
    ClipVoiceResponse,
    SubtitleStyleRequest,
    SubtitleStyleResponse,
)
from ...domain.jobs import JobCreate, JobType
from ...domain.organizations import MembershipRole
from ...repositories.clips import ClipsRepository
from ...repositories.jobs import JobsRepository
from ..dependencies import (
    get_clips_repository,
    get_jobs_repository,
    get_org_id,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_task_dispatcher,
)
from ...services.tasks import TaskDispatcher

router = APIRouter(prefix="/clips", tags=["clips"])


@router.patch(
    "/{clip_id}",
    response_model=ClipResponse,
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
async def update_clip(
    clip_id: UUID,
    payload: ClipUpdateRequest,
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    org_id: UUID = Depends(get_org_id),
) -> ClipResponse:
    clip = await clips_repo.get(clip_id=clip_id, org_id=org_id)
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    start_ms = payload.start_ms if payload.start_ms is not None else clip.start_ms
    end_ms = payload.end_ms if payload.end_ms is not None else clip.end_ms
    if start_ms >= end_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clip end time must be greater than start time",
        )

    updated = await clips_repo.update_metadata(
        clip_id=clip_id,
        org_id=org_id,
        title=payload.title,
        description=payload.description,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    return ClipResponse(data=updated)


@router.post(
    "/{clip_id}/subtitles:style",
    response_model=SubtitleStyleResponse,
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
async def style_clip_subtitles(
    clip_id: UUID,
    payload: SubtitleStyleRequest | None = None,
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("clips:style")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> SubtitleStyleResponse:
    cached = idempotency.get_response(SubtitleStyleResponse)
    if cached:
        return cached
    clip = await clips_repo.get(clip_id=clip_id, org_id=org_id)
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    request_payload = payload or SubtitleStyleRequest()
    updated_clip = await clips_repo.update_style_request(
        clip_id=clip.id,
        org_id=org_id,
        payload=request_payload,
    )
    if not updated_clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=clip.project_id,
            video_id=clip.video_id,
            clip_id=clip.id,
            job_type=JobType.SUBTITLE_RENDER,
        ),
    )

    response = SubtitleStyleResponse(
        job_id=job.id,
        clip_id=clip.id,
        style_status=updated_clip.style_status,
    )
    tasks.enqueue_subtitle_render(job_id=job.id, org_id=org_id)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.post(
    "/{clip_id}/tts",
    response_model=ClipVoiceResponse,
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
async def synthesize_clip_voice_over(
    clip_id: UUID,
    payload: ClipVoiceRequest | None = None,
    clips_repo: ClipsRepository = Depends(get_clips_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("clips:tts")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
) -> ClipVoiceResponse:
    cached = idempotency.get_response(ClipVoiceResponse)
    if cached:
        return cached
    clip = await clips_repo.get(clip_id=clip_id, org_id=org_id)
    if not clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    request_payload = payload or ClipVoiceRequest()
    updated_clip = await clips_repo.update_voice_request(
        clip_id=clip.id,
        org_id=org_id,
        payload=request_payload,
    )
    if not updated_clip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clip not found for organization",
        )

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=clip.project_id,
            video_id=clip.video_id,
            clip_id=clip.id,
            job_type=JobType.TTS_RENDER,
        ),
    )

    response = ClipVoiceResponse(
        job_id=job.id,
        clip_id=clip.id,
        voice_status=updated_clip.voice_status,
    )
    tasks.enqueue_tts(job_id=job.id, org_id=org_id)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response
