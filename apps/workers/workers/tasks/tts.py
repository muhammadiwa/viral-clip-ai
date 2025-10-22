"""Celery task that synthesises voice-over audio for clips using Coqui TTS."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import ffmpeg
import structlog
from TTS.api import TTS as CoquiTTS

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.clips import ClipVoiceStatus
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.clips import SqlAlchemyClipsRepository
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service
from apps.workers.workers.heuristics.audio import build_mix_profile

from .shared import update_job_status
from ..start import celery_app

logger = structlog.get_logger(__name__)

_session_factory = get_sessionmaker()
_storage: MinioStorageService | None = None
_tts_model: CoquiTTS | None = None


def _get_storage() -> MinioStorageService:
    global _storage
    if _storage is None:
        _storage = build_storage_service()
    return _storage


def _get_tts_model() -> CoquiTTS:
    global _tts_model
    if _tts_model is None:
        settings = get_settings()
        _tts_model = CoquiTTS(settings.tts_model_name)
    return _tts_model


def _collect_clip_text(transcripts, clip_start: int, clip_end: int) -> str:
    for candidate in reversed(transcripts):
        segments = candidate.aligned_segments or candidate.segments
        if not segments:
            continue
        selected = [
            segment.text.strip()
            for segment in segments
            if max(segment.start_ms, clip_start) < min(segment.end_ms, clip_end)
        ]
        if selected:
            return " ".join(selected)
    return ""


def _extract_audio_bed(source: Path, start_ms: int, end_ms: int, destination: Path) -> Path:
    duration = max(0.5, (end_ms - start_ms) / 1000.0)
    stream = (
        ffmpeg.input(str(source), ss=start_ms / 1000.0)
        .output(str(destination), t=duration, ac=2, ar=44100)
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Failed to extract audio bed for TTS mixing")
    return destination


def _mix_audio_tracks(
    bed_path: Path, voice_path: Path, destination: Path, settings
) -> Path:
    profile = build_mix_profile(settings)
    bed = ffmpeg.input(str(bed_path)).filter("volume", profile.bed_gain)
    voice = ffmpeg.input(str(voice_path)).filter("volume", profile.voice_gain)
    mixed = (
        ffmpeg.filter([bed, voice], "amix", inputs=2, dropout_transition=0)
        .filter(
            "loudnorm",
            I=profile.loudness_target_i,
            TP=profile.loudness_true_peak,
            LRA=profile.loudness_range,
        )
        .output(str(destination), format="wav", ac=2, ar=44100)
        .overwrite_output()
    )
    mixed.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Unable to mix narration with background audio")
    return destination


@celery_app.task(name="clips.tts")
def tts_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint that executes the TTS coroutine."""

    return asyncio.run(_tts_process(UUID(job_id), UUID(org_id)))


async def _tts_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.tts.start", job_id=str(job_id), org_id=str(org_id))
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
            videos_repo = SqlAlchemyVideosRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for TTS")
            if job.clip_id is None or job.video_id is None:
                raise RuntimeError("TTS job missing clip or video reference")

            clip = await clips_repo.get(clip_id=job.clip_id, org_id=org_id)
            if clip is None:
                raise RuntimeError("Clip not found for TTS job")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None or not video.upload_key:
                raise RuntimeError("Video source missing for TTS job")

            await clips_repo.update_voice_status(
                clip_id=clip.id,
                org_id=org_id,
                status=ClipVoiceStatus.SYNTHESIZING,
                error=None,
            )

            transcripts = await transcripts_repo.list_for_video(
                video_id=job.video_id, org_id=org_id
            )
            script_text = _collect_clip_text(transcripts, clip.start_ms, clip.end_ms)
            if not script_text:
                raise RuntimeError("No transcript content found for TTS synthesis")

            model = _get_tts_model()
            settings = get_settings()

            voice_size = 0
            mix_size = 0

            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                source_path = storage.download_to_path(
                    video.upload_key, temp_path / "source.mp4"
                )
                bed_path = _extract_audio_bed(
                    source_path, clip.start_ms, clip.end_ms, temp_path / "bed.wav"
                )
                voice_path = temp_path / f"clip-{clip.id}-voice.wav"
                mix_path = temp_path / f"clip-{clip.id}-mix.wav"
                kwargs: dict[str, object] = {
                    "text": script_text,
                    "file_path": str(voice_path),
                    "language": clip.voice_language or "en",
                }
                if clip.voice_name:
                    kwargs["speaker"] = clip.voice_name
                elif settings.tts_speaker_wav:
                    kwargs["speaker_wav"] = settings.tts_speaker_wav
                if clip.voice_settings:
                    if rate := clip.voice_settings.get("speaking_rate"):
                        kwargs["speed"] = float(rate)
                logger.debug("worker.tts.synthesize", clip_id=str(clip.id))
                model.tts_to_file(**kwargs)

                _mix_audio_tracks(bed_path, voice_path, mix_path, settings)

                object_key = storage.generate_object_key(
                    org_id=org_id,
                    project_id=clip.project_id,
                    suffix="tts",
                )
                storage.upload_file(
                    object_key,
                    voice_path,
                    content_type="audio/wav",
                )
                voice_size = voice_path.stat().st_size
                await artifacts_repo.create(
                    org_id=org_id,
                    payload=ArtifactCreate(
                        project_id=clip.project_id,
                        video_id=clip.video_id,
                        clip_id=clip.id,
                        kind=ArtifactKind.CLIP_AUDIO,
                        uri=storage.object_uri(object_key),
                        content_type="audio/wav",
                        size_bytes=voice_size,
                    ),
                )

                mix_object_key = storage.generate_object_key(
                    org_id=org_id,
                    project_id=clip.project_id,
                    suffix="tts-mix",
                )
                storage.upload_file(
                    mix_object_key,
                    mix_path,
                    content_type="audio/wav",
                )
                mix_size = mix_path.stat().st_size
                await artifacts_repo.create(
                    org_id=org_id,
                    payload=ArtifactCreate(
                        project_id=clip.project_id,
                        video_id=clip.video_id,
                        clip_id=clip.id,
                        kind=ArtifactKind.CLIP_AUDIO_MIX,
                        uri=storage.object_uri(mix_object_key),
                        content_type="audio/wav",
                        size_bytes=mix_size,
                    ),
                )

            duration_minutes = max(
                1, int(math.ceil((clip.end_ms - clip.start_ms) / 60000))
            )
            await billing_repo.record_usage(
                org_id,
                UsageIncrementRequest(
                    minutes_processed=duration_minutes,
                    storage_gb=(voice_size + mix_size) / float(1024**3),
                ),
            )

            await clips_repo.update_voice_status(
                clip_id=clip.id,
                org_id=org_id,
                status=ClipVoiceStatus.SYNTHESIZED,
                error=None,
            )

    except Exception as exc:
        logger.exception(
            "worker.tts.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        async with _session_factory() as session:
            clips_repo = SqlAlchemyClipsRepository(session)
            job = await SqlAlchemyJobsRepository(session).get(job_id=job_id, org_id=org_id)
            if job and job.clip_id:
                await clips_repo.update_voice_status(
                    clip_id=job.clip_id,
                    org_id=org_id,
                    status=ClipVoiceStatus.VOICE_FAILED,
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
    logger.info("worker.tts.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

