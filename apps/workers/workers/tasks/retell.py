"""Celery task that assembles narrative summaries for movie retell requests."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import structlog

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.domain.retells import RetellStatus, RetellUpdateRequest
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.retells import SqlAlchemyRetellsRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service

from .shared import update_job_status
from ..start import celery_app

logger = structlog.get_logger(__name__)

_session_factory = get_sessionmaker()
_storage: MinioStorageService | None = None


def _get_storage() -> MinioStorageService:
    global _storage
    if _storage is None:
        _storage = build_storage_service()
    return _storage

def _summarise(text: str, sentence_target: int) -> tuple[str, list[str]]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return "", []
    top_sentences = sentences[: sentence_target * 3]
    scored = sorted(top_sentences, key=len, reverse=True)[:sentence_target]
    ordered = sorted(scored, key=lambda s: top_sentences.index(s))
    summary = " ".join(ordered)

    chunk_size = max(1, math.ceil(len(sentences) / max(4, sentence_target // 2)))
    outline: list[str] = []
    for index in range(0, len(sentences), chunk_size):
        chunk = sentences[index : index + chunk_size]
        if not chunk:
            continue
        outline.append(" ".join(chunk[:2]))
    return summary, outline[: sentence_target]


@celery_app.task(name="retell.generate")
def retell_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint that executes the retell coroutine."""

    return asyncio.run(_retell_process(UUID(job_id), UUID(org_id)))


async def _retell_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.retell.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            retells_repo = SqlAlchemyRetellsRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            artifacts_repo = SqlAlchemyArtifactsRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None or job.retell_id is None:
                raise RuntimeError("Retell job not found")

            retell = await retells_repo.get(retell_id=job.retell_id, org_id=org_id)
            if retell is None:
                raise RuntimeError("Retell record missing for job")

            await retells_repo.update_status(
                retell_id=retell.id,
                org_id=org_id,
                status=RetellStatus.GENERATING,
                message="Generating condensed narrative",
                error=None,
            )

            videos = await videos_repo.list_for_project(
                project_id=retell.project_id, org_id=org_id
            )
            transcript_text = ""
            for video in videos:
                transcripts = await transcripts_repo.list_for_video(
                    video_id=video.id, org_id=org_id
                )
                for transcript in transcripts:
                    segments = transcript.aligned_segments or transcript.segments
                    if not segments:
                        continue
                    transcript_text += " " + " ".join(
                        segment.text.strip() for segment in segments if segment.text
                    )

            if not transcript_text.strip():
                raise RuntimeError("No transcript material available for retell")

            settings = get_settings()
            summary, outline = _summarise(
                transcript_text, settings.retell_summary_sentences
            )
            if not summary:
                raise RuntimeError("Unable to assemble retell summary")

            await retells_repo.update_details(
                retell_id=retell.id,
                org_id=org_id,
                payload=RetellUpdateRequest(
                    summary=summary,
                    outline=outline,
                    status_message="Summary ready",
                ),
            )

            await retells_repo.update_status(
                retell_id=retell.id,
                org_id=org_id,
                status=RetellStatus.READY,
                message="Narrative generated",
                error=None,
            )

            script_size = 0

            with TemporaryDirectory() as temp_dir:
                script_path = Path(temp_dir) / f"retell-{retell.id}.txt"
                script_path.write_text(summary + "\n\n" + "\n".join(outline), encoding="utf-8")
                object_key = storage.generate_object_key(
                    org_id=org_id,
                    project_id=retell.project_id,
                    suffix="retell-script",
                )
                storage.upload_file(
                    object_key,
                    script_path,
                    content_type="text/plain",
                )
                script_size = script_path.stat().st_size
                await artifacts_repo.create(
                    org_id=org_id,
                    payload=ArtifactCreate(
                        project_id=retell.project_id,
                        video_id=None,
                        clip_id=None,
                        retell_id=retell.id,
                        kind=ArtifactKind.RETELL_SCRIPT,
                        uri=storage.object_uri(object_key),
                        content_type="text/plain",
                        size_bytes=script_size,
                    ),
                )

            await billing_repo.record_usage(
                org_id,
                UsageIncrementRequest(
                    retells_created=1,
                    storage_gb=script_size / float(1024**3),
                ),
            )

    except Exception as exc:
        logger.exception(
            "worker.retell.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        async with _session_factory() as session:
            retells_repo = SqlAlchemyRetellsRepository(session)
            job = await SqlAlchemyJobsRepository(session).get(job_id=job_id, org_id=org_id)
            if job and job.retell_id:
                await retells_repo.update_status(
                    retell_id=job.retell_id,
                    org_id=org_id,
                    status=RetellStatus.FAILED,
                    message="Retell generation failed",
                    error=str(exc),
                )
        await update_job_status(
            org_id=org_id,
            job_id=job_id,
            status=JobStatus.FAILED,
            message=str(exc),
        )
        raise

    await update_job_status(
        org_id=org_id,
        job_id=job_id,
        status=JobStatus.SUCCEEDED,
        progress=1.0,
    )
    logger.info("worker.retell.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

