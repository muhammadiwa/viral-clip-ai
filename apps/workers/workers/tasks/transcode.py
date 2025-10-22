"""Celery task that transcodes uploaded videos into HLS previews."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import ffmpeg
import structlog

from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
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


def _transcode_to_hls(source: Path, output_dir: Path) -> Path:
    """Run ffmpeg to produce an HLS playlist for the given source file."""

    output_dir.mkdir(parents=True, exist_ok=True)
    playlist_path = output_dir / "index.m3u8"
    segment_pattern = output_dir / "segment%03d.ts"
    stream = (
        ffmpeg.input(str(source))
        .output(
            str(playlist_path),
            format="hls",
            hls_time=6,
            hls_playlist_type="vod",
            hls_segment_filename=str(segment_pattern),
            vcodec="h264",
            acodec="aac",
            video_bitrate="3000k",
            audio_bitrate="128k",
            preset="veryfast",
        )
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not playlist_path.exists():
        raise RuntimeError("ffmpeg did not produce an HLS manifest")
    return playlist_path


def _content_type_for(path: Path) -> str:
    if path.suffix == ".m3u8":
        return "application/x-mpegURL"
    if path.suffix == ".ts":
        return "video/mp2t"
    return "application/octet-stream"


@celery_app.task(name="transcode.process")
def transcode_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint that bridges into the async transcode coroutine."""

    return asyncio.run(_transcode_process(UUID(job_id), UUID(org_id)))


async def _transcode_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.transcode.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()
    storage.ensure_bucket()

    playlist_uri: str | None = None

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)
            artifacts_repo = SqlAlchemyArtifactsRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for transcode")
            if job.video_id is None:
                raise RuntimeError("Transcode job missing video reference")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None:
                raise RuntimeError("Video not found during transcode")
            if not video.upload_key:
                raise RuntimeError("Video does not have an upload key to transcode")

            duration_seconds = 0.0
            frame_rate: float | None = None
            width: int | None = None
            height: int | None = None
            total_size = 0

            with TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                source_path = storage.download_to_path(
                    video.upload_key, temp_dir_path / "source.mp4"
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.25,
                )
                playlist_path = _transcode_to_hls(source_path, temp_dir_path / "hls")
                try:
                    probe = ffmpeg.probe(str(source_path))
                    duration_seconds = float(
                        probe.get("format", {}).get("duration") or 0.0
                    )
                    video_stream = next(
                        (
                            stream
                            for stream in probe.get("streams", [])
                            if stream.get("codec_type") == "video"
                        ),
                        {},
                    )
                    width = (
                        int(video_stream.get("width"))
                        if video_stream.get("width")
                        else None
                    )
                    height = (
                        int(video_stream.get("height"))
                        if video_stream.get("height")
                        else None
                    )
                    rate = video_stream.get("r_frame_rate")
                    if rate and rate != "0/0":
                        num, den = rate.split("/")
                        if float(den):
                            frame_rate = float(num) / float(den)
                except ffmpeg.Error as exc:  # pragma: no cover - metadata enrichment
                    logger.warning(
                        "worker.transcode.probe_failed",
                        job_id=str(job_id),
                        org_id=str(org_id),
                        error=exc.stderr.decode("utf-8", "ignore") if exc.stderr else str(exc),
                    )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.6,
                )

                prefix = storage.generate_object_key(
                    org_id=org_id,
                    project_id=video.project_id,
                    suffix="hls",
                )
                for file_path in (temp_dir_path / "hls").rglob("*"):
                    if not file_path.is_file():
                        continue
                    object_key = f"{prefix}/{file_path.relative_to(temp_dir_path / 'hls').as_posix()}"
                    storage.upload_file(
                        object_key,
                        file_path,
                        content_type=_content_type_for(file_path),
                    )
                    total_size += file_path.stat().st_size

            playlist_uri = storage.object_uri(f"{prefix}/index.m3u8")
            await artifacts_repo.create(
                org_id=org_id,
                payload=ArtifactCreate(
                    project_id=video.project_id,
                    video_id=video.id,
                    clip_id=None,
                    retell_id=None,
                    kind=ArtifactKind.VIDEO_PREVIEW,
                    uri=playlist_uri,
                    content_type="application/x-mpegURL",
                    size_bytes=total_size,
                ),
            )
            await videos_repo.update_metadata(
                video_id=video.id,
                org_id=org_id,
                duration_ms=int(duration_seconds * 1000) if duration_seconds else None,
                frame_rate=frame_rate,
                width=width,
                height=height,
            )
            minutes_processed = (
                int(math.ceil(duration_seconds / 60)) if duration_seconds > 0 else 0
            )
            storage_gb = total_size / float(1024**3)
            await billing_repo.record_usage(
                org_id,
                UsageIncrementRequest(
                    minutes_processed=minutes_processed,
                    storage_gb=storage_gb,
                ),
            )
    except Exception as exc:
        logger.exception(
            "worker.transcode.failed",
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

    if playlist_uri is None:
        raise RuntimeError("Transcode did not produce an HLS artifact")

    await update_job_status(
        org_id=org_id,
        job_id=job_id,
        status=JobStatus.SUCCEEDED,
        progress=1.0,
    )
    logger.info(
        "worker.transcode.complete",
        job_id=str(job_id),
        org_id=str(org_id),
        playlist_uri=playlist_uri,
    )
    return {
        "job_id": str(job_id),
        "org_id": str(org_id),
        "playlist_uri": playlist_uri,
        "artifact_kind": ArtifactKind.VIDEO_PREVIEW.value,
    }
