"""Celery task responsible for final project export rendering."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from uuid import UUID

import ffmpeg
import math
import structlog

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
from apps.api.app.repositories.clips import SqlAlchemyClipsRepository
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.projects import SqlAlchemyProjectsRepository
from apps.api.app.repositories.branding import SqlAlchemyBrandKitRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service
from apps.workers.workers.heuristics.export import watermark_position

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


def _download_brand_segment(
    storage: MinioStorageService,
    object_key: Optional[str],
    temp_path: Path,
    name: str,
) -> Optional[Path]:
    if not object_key:
        return None
    target = temp_path / f"{name}.mp4"
    try:
        return storage.download_to_path(object_key, target)
    except Exception as exc:  # pragma: no cover - remote dependency
        logger.warning(
            "worker.export.brand_segment_missing",
            object_key=object_key,
            error=str(exc),
        )
        return None


def _apply_watermark(
    storage: MinioStorageService,
    source: Path,
    destination: Path,
    *,
    object_key: Optional[str],
    position: str,
    scale: float,
    preset: str,
) -> Path:
    if not object_key:
        return source
    watermark_path = storage.download_to_path(
        object_key, destination.parent / "watermark.png"
    )
    x_expr, y_expr = watermark_position(position)
    video_input = ffmpeg.input(str(source))
    watermark_input = ffmpeg.input(str(watermark_path))
    scaled_overlay = watermark_input.filter("scale", f"iw*{scale}", f"ih*{scale}")
    overlay = ffmpeg.overlay(video_input.video, scaled_overlay, x=x_expr, y=y_expr)
    stream = (
        ffmpeg.output(
            overlay.filter("format", "yuv420p"),
            video_input.audio,
            str(destination),
            vcodec="libx264",
            acodec="aac",
            preset=preset,
            movflags="+faststart",
        )
        .overwrite_output()
    )
    try:
        stream.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error:
        # Retry without audio stream for silent sources
        stream = (
            ffmpeg.output(
                overlay.filter("format", "yuv420p"),
                str(destination),
                vcodec="libx264",
                preset=preset,
                movflags="+faststart",
            )
            .overwrite_output()
        )
        stream.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Failed to apply watermark overlay to export")
    return destination


def _probe_duration_ms(path: Path) -> int:
    try:
        metadata = ffmpeg.probe(str(path))
        duration = float(metadata.get("format", {}).get("duration", 0.0))
        return int(duration * 1000)
    except (ffmpeg.Error, ValueError, TypeError):  # pragma: no cover - ffprobe guard
        return 0


def _render_clip_segment(source: Path, start_ms: int, end_ms: int, destination: Path) -> None:
    duration = max(0.5, (end_ms - start_ms) / 1000.0)
    stream = (
        ffmpeg.input(str(source), ss=start_ms / 1000.0)
        .output(str(destination), t=duration, c="copy")
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Failed to render clip segment during export")


def _concat_segments(segment_paths: list[Path], output_path: Path, preset: str) -> None:
    concat_list = output_path.parent / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{path}'" for path in segment_paths), encoding="utf-8"
    )
    stream = (
        ffmpeg.input(str(concat_list), format="concat", safe=0)
        .output(str(output_path), c="copy", preset=preset)
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not output_path.exists():
        raise RuntimeError("Failed to assemble export video")


@celery_app.task(name="projects.export")
def project_export_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint for project export rendering."""

    return asyncio.run(_project_export_process(UUID(job_id), UUID(org_id)))


async def _project_export_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.export.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            projects_repo = SqlAlchemyProjectsRepository(session)
            brand_repo = SqlAlchemyBrandKitRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)
            clips_repo = SqlAlchemyClipsRepository(session)
            artifacts_repo = SqlAlchemyArtifactsRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None or job.project_id is None:
                raise RuntimeError("Export job not found")

            project = await projects_repo.get(project_id=job.project_id, org_id=org_id)
            if project is None:
                raise RuntimeError("Project not found for export")

            videos = await videos_repo.list_for_project(
                project_id=project.id, org_id=org_id
            )
            if not videos:
                raise RuntimeError("Project has no videos to export")

            primary_video = videos[0]
            if not primary_video.upload_key:
                raise RuntimeError("Primary video missing source media for export")

            clips = await clips_repo.list_for_video(
                video_id=primary_video.id, org_id=org_id
            )
            if not clips:
                raise RuntimeError("No clips available to assemble export")

            settings = get_settings().model_copy(deep=True)
            if project.brand_kit_id:
                brand_kit = await brand_repo.get(org_id, project.brand_kit_id)
            else:
                brand_kit = None
            if brand_kit:
                if brand_kit.intro_object_key:
                    settings.export_brand_intro_object_key = brand_kit.intro_object_key
                if brand_kit.outro_object_key:
                    settings.export_brand_outro_object_key = brand_kit.outro_object_key
                if brand_kit.watermark_object_key:
                    settings.export_watermark_object_key = brand_kit.watermark_object_key
                if brand_kit.primary_color:
                    settings.subtitle_brand_text_color = brand_kit.primary_color
                if brand_kit.secondary_color:
                    settings.subtitle_brand_background_color = brand_kit.secondary_color
                if brand_kit.accent_color:
                    settings.subtitle_brand_highlight_color = brand_kit.accent_color
            if project.brand_overrides:
                for key, value in project.brand_overrides.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)

            export_size = 0
            total_duration_ms = sum(
                max(0, clip.end_ms - clip.start_ms) for clip in clips
            )

            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                source = storage.download_to_path(
                    primary_video.upload_key, temp_path / "source.mp4"
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.3,
                )

                segments: list[Path] = []
                brand_intro_path = _download_brand_segment(
                    storage,
                    settings.export_brand_intro_object_key,
                    temp_path,
                    "brand-intro",
                )
                if brand_intro_path:
                    segments.append(brand_intro_path)
                    total_duration_ms += _probe_duration_ms(brand_intro_path)
                for index, clip in enumerate(clips, start=1):
                    segment_path = temp_path / f"segment-{index}.mp4"
                    _render_clip_segment(
                        source, clip.start_ms, clip.end_ms, segment_path
                    )
                    segments.append(segment_path)

                brand_outro_path = _download_brand_segment(
                    storage,
                    settings.export_brand_outro_object_key,
                    temp_path,
                    "brand-outro",
                )
                if brand_outro_path:
                    segments.append(brand_outro_path)
                    total_duration_ms += _probe_duration_ms(brand_outro_path)

                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.6,
                )

                export_path = temp_path / "export.mp4"
                _concat_segments(segments, export_path, settings.export_video_preset)

                final_path = _apply_watermark(
                    storage,
                    export_path,
                    temp_path / "export-branded.mp4",
                    object_key=settings.export_watermark_object_key,
                    position=settings.export_watermark_position,
                    scale=settings.export_watermark_scale,
                    preset=settings.export_video_preset,
                )

                object_key = storage.generate_object_key(
                    org_id=org_id,
                    project_id=project.id,
                    suffix="export",
                )
                storage.upload_file(
                    object_key,
                    final_path,
                    content_type="video/mp4",
                )
                export_size = final_path.stat().st_size
                await artifacts_repo.create(
                    org_id=org_id,
                    payload=ArtifactCreate(
                        project_id=project.id,
                        video_id=primary_video.id,
                        clip_id=None,
                        kind=ArtifactKind.VIDEO_EXPORT,
                        uri=storage.object_uri(object_key),
                        content_type="video/mp4",
                        size_bytes=export_size,
                    ),
                )

            await billing_repo.record_usage(
                org_id,
                UsageIncrementRequest(
                    minutes_processed=max(
                        1, int(math.ceil(total_duration_ms / 60000))
                    ),
                    storage_gb=export_size / float(1024**3),
                ),
            )

    except Exception as exc:
        logger.exception(
            "worker.export.failed",
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

    await update_job_status(
        org_id=org_id,
        job_id=job_id,
        status=JobStatus.SUCCEEDED,
        progress=1.0,
    )
    logger.info("worker.export.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

