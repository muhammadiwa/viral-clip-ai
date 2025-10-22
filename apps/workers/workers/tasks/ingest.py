"""Celery task that prepares uploaded or remote videos for downstream processing."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import structlog
import yt_dlp

from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.domain.videos import VideoSourceType
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
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


def _download_youtube_source(url: str, directory: Path) -> Path:
    """Download a YouTube video to the provided directory and return the file path."""

    directory.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as downloader:
        downloader.download([url])
    mp4_files = list(directory.glob("*.mp4"))
    if not mp4_files:
        raise RuntimeError("Unable to download YouTube source")
    return mp4_files[0]


@celery_app.task(name="ingest.process")
def ingest_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint that bridges into the async ingest coroutine."""

    return asyncio.run(_ingest_process(UUID(job_id), UUID(org_id)))


async def _ingest_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.ingest.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05)
    storage = _get_storage()
    storage.ensure_bucket()

    upload_key: str | None = None

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for ingest")
            if job.video_id is None:
                raise RuntimeError("Ingest job missing video reference")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None:
                raise RuntimeError("Video not found during ingest")

            if video.source_type == VideoSourceType.UPLOAD:
                if not video.upload_key:
                    raise RuntimeError("Uploaded video is missing storage key")
                if not storage.object_exists(video.upload_key):
                    raise RuntimeError("Uploaded source object not found in storage")
                logger.info(
                    "worker.ingest.upload_verified",
                    job_id=str(job_id),
                    object_key=video.upload_key,
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.6,
                )
                upload_key = video.upload_key
            elif video.source_type == VideoSourceType.YOUTUBE:
                if not video.source_url:
                    raise RuntimeError("YouTube ingest requires a source_url")
                with TemporaryDirectory() as temp_dir:
                    temp_path = _download_youtube_source(video.source_url, Path(temp_dir))
                    upload_key = storage.generate_object_key(
                        org_id=org_id,
                        project_id=video.project_id,
                        suffix="source",
                    )
                    storage.upload_file(upload_key, temp_path, content_type="video/mp4")
                    await videos_repo.set_upload_key(
                        video_id=video.id, org_id=org_id, upload_key=upload_key
                    )
                    logger.info(
                        "worker.ingest.youtube_uploaded",
                        job_id=str(job_id),
                        object_key=upload_key,
                    )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.7,
                )
            else:
                raise RuntimeError(f"Unhandled video source type: {video.source_type}")

    except Exception as exc:
        logger.exception(
            "worker.ingest.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        await update_job_status(
            org_id=org_id,
            job_id=job_id,
            status=JobStatus.FAILED,
            message=str(exc),
        )
        raise

    if upload_key is None:
        raise RuntimeError("Ingest completed without producing an upload key")

    await update_job_status(
        org_id=org_id,
        job_id=job_id,
        status=JobStatus.SUCCEEDED,
        progress=1.0,
    )
    logger.info(
        "worker.ingest.complete",
        job_id=str(job_id),
        org_id=str(org_id),
        upload_key=upload_key,
    )
    return {"job_id": str(job_id), "org_id": str(org_id), "upload_key": upload_key}
