"""Celery task that renders animated subtitle files for generated clips."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import structlog
import pysubs2

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.clips import ClipStyleStatus
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
from apps.api.app.repositories.clips import SqlAlchemyClipsRepository
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.projects import SqlAlchemyProjectsRepository
from apps.api.app.repositories.branding import SqlAlchemyBrandKitRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service
from apps.workers.workers.heuristics.subtitles import resolve_style

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


def _hex_to_color(value: str | None, fallback: str) -> pysubs2.Color:
    try:
        return pysubs2.Color(value or fallback)
    except ValueError:
        return pysubs2.Color(fallback)


def _format_segment_text(segment, style: dict[str, object]) -> str:
    text = segment.text.replace("\n", " ").strip()
    if style.get("karaoke") and segment.words:
        parts: list[str] = []
        for word in segment.words:
            duration_cs = max(1, int((word.end_ms - word.start_ms) / 10))
            parts.append(f"{{\\kf{duration_cs}}}{word.word}")
        text = "".join(parts)
    if style.get("uppercase"):
        text = text.upper()
    fade_in = int(style.get("fade_in_ms", 0))
    fade_out = int(style.get("fade_out_ms", 0))
    if fade_in > 0 or fade_out > 0:
        text = f"{{\\fad({fade_in},{fade_out})}}{text}"
    return text


def _build_subtitle_file(
    *,
    clip_start: int,
    clip_end: int,
    preset: str | None,
    overrides: dict[str, object],
    segments,
) -> pysubs2.SSAFile:
    settings = get_settings()
    style_config = resolve_style(preset, overrides, settings=settings)
    subs = pysubs2.SSAFile()
    style = pysubs2.SSAStyle(
        fontname=str(style_config.get("font_family")),
        fontsize=float(style_config.get("font_size", 48)),
        primarycolor=_hex_to_color(
            str(style_config.get("text_color")), "#FFFFFF"
        ),
        backcolor=_hex_to_color(
            str(style_config.get("background_color")), "#00000000"
        ),
        outlinecolor=_hex_to_color(
            str(style_config.get("stroke_color")), "#000000"
        ),
        secondarycolor=_hex_to_color(
            str(style_config.get("highlight_color")), "#FFFFFF"
        ),
        outline=float(style_config.get("outline", 2)),
        shadow=float(style_config.get("shadow", 1)),
        alignment=int(style_config.get("alignment", 2)),
        marginl=int(style_config.get("margin_horizontal", 40)),
        marginr=int(style_config.get("margin_horizontal", 40)),
        marginv=int(style_config.get("margin_vertical", 60)),
        bold=-1 if style_config.get("bold") else 0,
        italic=-1 if style_config.get("italic") else 0,
        underline=-1 if style_config.get("underline") else 0,
    )
    subs.styles["ViralClip"] = style

    for segment in segments:
        overlap_start = max(segment.start_ms, clip_start)
        overlap_end = min(segment.end_ms, clip_end)
        if overlap_start >= overlap_end:
            continue
        start = max(0, overlap_start - clip_start)
        end = max(start + 250, overlap_end - clip_start)
        text = _format_segment_text(segment, style_config)
        if not text:
            continue
        subs.events.append(
            pysubs2.SSAEvent(
                start=start / 1000.0,
                end=end / 1000.0,
                text=text,
                style="ViralClip",
                effect="karaoke" if style_config.get("karaoke") else None,
            )
        )
    subs.sort()
    return subs


@celery_app.task(name="clips.subtitle_render")
def subtitle_render_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint for subtitle rendering."""

    return asyncio.run(_subtitle_render_process(UUID(job_id), UUID(org_id)))


async def _subtitle_render_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.subtitle.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            clips_repo = SqlAlchemyClipsRepository(session)
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            artifacts_repo = SqlAlchemyArtifactsRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)
            projects_repo = SqlAlchemyProjectsRepository(session)
            brand_repo = SqlAlchemyBrandKitRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for subtitle rendering")
            if job.clip_id is None or job.video_id is None:
                raise RuntimeError("Subtitle job missing clip or video reference")

            clip = await clips_repo.get(clip_id=job.clip_id, org_id=org_id)
            if clip is None:
                raise RuntimeError("Clip not found for subtitle rendering")

            await clips_repo.update_style_status(
                clip_id=clip.id,
                org_id=org_id,
                status=ClipStyleStatus.STYLING,
                error=None,
            )

            transcripts = await transcripts_repo.list_for_video(
                video_id=job.video_id, org_id=org_id
            )
            if not transcripts:
                raise RuntimeError("No transcripts available for subtitle rendering")

            transcript = None
            for candidate in reversed(transcripts):
                if candidate.aligned_segments:
                    transcript = candidate
                    segments = candidate.aligned_segments
                    break
                if candidate.segments:
                    transcript = candidate
                    segments = candidate.segments
            if transcript is None:
                raise RuntimeError("Transcript segments missing for subtitle rendering")

            project = await projects_repo.get(job.project_id, org_id)
            brand_kit = None
            if project and project.brand_kit_id:
                brand_kit = await brand_repo.get(org_id, project.brand_kit_id)

            settings = get_settings().model_copy(deep=True)
            if brand_kit:
                if brand_kit.font_family:
                    settings.subtitle_brand_font_family = brand_kit.font_family
                if brand_kit.primary_color:
                    settings.subtitle_brand_text_color = brand_kit.primary_color
                if brand_kit.secondary_color:
                    settings.subtitle_brand_background_color = brand_kit.secondary_color
                if brand_kit.accent_color:
                    settings.subtitle_brand_highlight_color = brand_kit.accent_color
            if project and project.brand_overrides:
                for key, value in project.brand_overrides.items():
                    setattr(settings, key, value)

            brand_style = dict(brand_kit.subtitle_overrides if brand_kit else {})
            if project and project.brand_overrides:
                brand_style.update(project.brand_overrides)

            clip_style_overrides = dict(clip.style_settings or {})
            preset = (
                clip.style_preset
                or clip_style_overrides.pop("preset", None)
                or brand_style.pop("preset", None)
                or settings.subtitle_default_preset
            )
            style_overrides = {**brand_style, **clip_style_overrides}

            subs = _build_subtitle_file(
                clip_start=clip.start_ms,
                clip_end=clip.end_ms,
                preset=preset,
                overrides=style_overrides,
                segments=segments,
            )

            subtitle_size = 0

            with TemporaryDirectory() as temp_dir:
                output_path = Path(temp_dir) / f"clip-{clip.id}.ass"
                subs.save(str(output_path))
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.6,
                )
                object_key = storage.generate_object_key(
                    org_id=org_id,
                    project_id=clip.project_id,
                    suffix="subtitles",
                )
                storage.upload_file(
                    object_key,
                    output_path,
                    content_type="text/x-ssa",
                )
                subtitle_size = output_path.stat().st_size
                await artifacts_repo.create(
                    org_id=org_id,
                    payload=ArtifactCreate(
                        project_id=clip.project_id,
                        video_id=clip.video_id,
                        clip_id=clip.id,
                        kind=ArtifactKind.CLIP_SUBTITLE,
                        uri=storage.object_uri(object_key),
                        content_type="text/x-ssa",
                        size_bytes=subtitle_size,
                    ),
                )

            await billing_repo.record_usage(
                org_id,
                UsageIncrementRequest(
                    storage_gb=subtitle_size / float(1024**3),
                ),
            )

            await clips_repo.update_style_status(
                clip_id=clip.id,
                org_id=org_id,
                status=ClipStyleStatus.STYLED,
                error=None,
            )

    except Exception as exc:
        logger.exception(
            "worker.subtitle.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        async with _session_factory() as session:
            clips_repo = SqlAlchemyClipsRepository(session)
            job = await SqlAlchemyJobsRepository(session).get(job_id=job_id, org_id=org_id)
            if job and job.clip_id:
                await clips_repo.update_style_status(
                    clip_id=job.clip_id,
                    org_id=org_id,
                    status=ClipStyleStatus.STYLE_FAILED,
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
    logger.info("worker.subtitle.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

