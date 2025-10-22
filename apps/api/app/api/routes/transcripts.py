from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ...domain.jobs import JobCreate, JobType
from ...domain.organizations import MembershipRole
from ...domain.pagination import PaginationParams
from ...domain.transcripts import (
    AlignmentStatus,
    Transcript,
    TranscriptAlignmentResponse,
    TranscriptCreationResponse,
    TranscriptListResponse,
    TranscriptRequest,
    TranscriptResponse,
    TranscriptStatus,
    TranscriptUpdateRequest,
    TranscriptCreate,
)
from ...domain.videos import VideoStatus
from ...repositories.jobs import JobsRepository
from ...repositories.transcripts import TranscriptsRepository
from ...repositories.videos import VideosRepository
from ...services.pagination import paginate_sequence
from ...services.tasks import TaskDispatcher
from ..dependencies import (
    get_active_membership,
    get_jobs_repository,
    get_org_id,
    get_transcripts_repository,
    get_videos_repository,
    require_org_role,
    enforce_rate_limit,
    get_idempotency_context,
    IdempotencyContext,
    get_pagination_params,
    get_task_dispatcher,
)

router = APIRouter(prefix="/videos", tags=["transcripts"])


@router.post(
    "/{video_id}/transcripts",
    response_model=TranscriptCreationResponse,
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
async def request_transcription(
    video_id: UUID,
    payload: TranscriptRequest,
    videos_repo: VideosRepository = Depends(get_videos_repository),
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("transcripts:create")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> TranscriptCreationResponse:
    cached = idempotency.get_response(TranscriptCreationResponse)
    if cached:
        return cached
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    if video.status not in {
        VideoStatus.READY_FOR_TRANSCRIPTION,
        VideoStatus.TRANSCRIPTION_FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is not ready for transcription",
        )

    await videos_repo.update_status(
        video_id=video.id,
        org_id=org_id,
        status=VideoStatus.TRANSCRIPTION_QUEUED,
    )

    transcript = await transcripts_repo.create(
        org_id=org_id,
        payload=TranscriptCreate(
            project_id=video.project_id,
            video_id=video.id,
            language_code=payload.language_code,
            prompt=payload.prompt,
        ),
    )
    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=video.project_id,
            video_id=video.id,
            transcript_id=transcript.id,
            job_type=JobType.TRANSCRIPTION,
        ),
    )
    tasks.enqueue_transcription(job_id=job.id, org_id=org_id)

    response = TranscriptCreationResponse(transcript=transcript, job_id=job.id)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.get(
    "/{video_id}/transcripts",
    response_model=TranscriptListResponse,
    dependencies=[Depends(get_active_membership)],
)
async def list_transcripts(
    video_id: UUID,
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
    pagination: PaginationParams = Depends(get_pagination_params),
) -> TranscriptListResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    transcripts = await transcripts_repo.list_for_video(video_id=video_id, org_id=org_id)
    paginated, meta = paginate_sequence(transcripts, pagination)
    return TranscriptListResponse(data=paginated, count=meta.count, pagination=meta)


async def _get_transcript_or_404(
    *,
    transcripts_repo: TranscriptsRepository,
    transcript_id: UUID,
    org_id: UUID,
) -> Transcript:
    transcript = await transcripts_repo.get(transcript_id=transcript_id, org_id=org_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )
    return transcript


@router.get(
    "/{video_id}/transcripts/{transcript_id}",
    response_model=TranscriptResponse,
    dependencies=[Depends(get_active_membership)],
)
async def get_transcript(
    video_id: UUID,
    transcript_id: UUID,
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
) -> TranscriptResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    transcript = await _get_transcript_or_404(
        transcripts_repo=transcripts_repo,
        transcript_id=transcript_id,
        org_id=org_id,
    )
    if transcript.video_id != video.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found for video",
        )
    return TranscriptResponse(data=transcript)


@router.post(
    "/{video_id}/transcripts/{transcript_id}:align",
    response_model=TranscriptAlignmentResponse,
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
async def request_alignment(
    video_id: UUID,
    transcript_id: UUID,
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    jobs_repo: JobsRepository = Depends(get_jobs_repository),
    tasks: TaskDispatcher = Depends(get_task_dispatcher),
    org_id: UUID = Depends(get_org_id),
    _: object = Depends(enforce_rate_limit("transcripts:align")),
    idempotency: IdempotencyContext = Depends(get_idempotency_context),
) -> TranscriptAlignmentResponse:
    cached = idempotency.get_response(TranscriptAlignmentResponse)
    if cached:
        return cached
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    if video.status not in {
        VideoStatus.READY_FOR_ALIGNMENT,
        VideoStatus.ALIGNMENT_FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is not ready for alignment",
        )

    transcript = await _get_transcript_or_404(
        transcripts_repo=transcripts_repo,
        transcript_id=transcript_id,
        org_id=org_id,
    )
    if transcript.video_id != video.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found for video",
        )

    if transcript.status != TranscriptStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transcript is not ready for alignment",
        )

    if transcript.alignment_status not in {
        AlignmentStatus.NOT_REQUESTED,
        AlignmentStatus.FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alignment already in progress",
        )

    await transcripts_repo.update_alignment(
        transcript_id=transcript.id,
        org_id=org_id,
        status=AlignmentStatus.QUEUED,
        error=None,
    )

    await videos_repo.update_status(
        video_id=video.id,
        org_id=org_id,
        status=VideoStatus.ALIGNMENT_QUEUED,
    )

    job = await jobs_repo.create(
        org_id=org_id,
        payload=JobCreate(
            project_id=video.project_id,
            video_id=video.id,
            transcript_id=transcript.id,
            job_type=JobType.ALIGNMENT,
        ),
    )

    transcript = await transcripts_repo.get(transcript_id=transcript.id, org_id=org_id)
    response = TranscriptAlignmentResponse(transcript=transcript, job_id=job.id)
    tasks.enqueue_alignment(job_id=job.id, org_id=org_id)
    await idempotency.store_response(response, status_code=status.HTTP_202_ACCEPTED)
    return response


@router.patch(
    "/{video_id}/transcripts/{transcript_id}",
    response_model=TranscriptResponse,
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
async def update_transcript(
    video_id: UUID,
    transcript_id: UUID,
    payload: TranscriptUpdateRequest,
    transcripts_repo: TranscriptsRepository = Depends(get_transcripts_repository),
    videos_repo: VideosRepository = Depends(get_videos_repository),
    org_id: UUID = Depends(get_org_id),
) -> TranscriptResponse:
    video = await videos_repo.get(video_id=video_id, org_id=org_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    transcript = await _get_transcript_or_404(
        transcripts_repo=transcripts_repo,
        transcript_id=transcript_id,
        org_id=org_id,
    )
    if transcript.video_id != video.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found for video",
        )

    updated = transcript
    if payload.status is not None or payload.segments is not None or payload.transcription_error is not None:
        updated = await transcripts_repo.update_transcription(
            transcript_id=transcript.id,
            org_id=org_id,
            status=payload.status,
            segments=payload.segments,
            error=payload.transcription_error,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    if payload.alignment_status is not None or payload.aligned_segments is not None or payload.alignment_error is not None:
        updated = await transcripts_repo.update_alignment(
            transcript_id=transcript_id,
            org_id=org_id,
            status=payload.alignment_status,
            segments=payload.aligned_segments,
            error=payload.alignment_error,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found")

    return TranscriptResponse(data=updated)

