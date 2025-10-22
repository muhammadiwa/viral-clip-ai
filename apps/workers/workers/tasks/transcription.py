"""Celery tasks responsible for automated transcription and alignment prep."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from uuid import UUID

import ffmpeg
import structlog
from faster_whisper import WhisperModel

from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.domain.transcripts import (
    TranscriptSegment,
    TranscriptStatus,
    TranscriptWord,
)
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service
from apps.api.app.core.config import get_settings

from .shared import update_job_status
from ..start import celery_app

logger = structlog.get_logger(__name__)

_session_factory = get_sessionmaker()
_storage: MinioStorageService | None = None
_whisper_model: WhisperModel | None = None


def _get_storage() -> MinioStorageService:
    global _storage
    if _storage is None:
        _storage = build_storage_service()
    return _storage


def _get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        settings = get_settings()
        _whisper_model = WhisperModel(
            settings.whisper_model_name,
            compute_type=settings.whisper_compute_type,
        )
    return _whisper_model


def _confidence_from_logprob(logprob: float | None) -> float | None:
    if logprob is None:
        return None
    # Map average log probability (typically -5..0) into a 0..1 heuristic range.
    score = 1.0 + (logprob / 5.0)
    return max(0.0, min(1.0, score))


def _convert_segment_words(words: Iterable[object]) -> list[TranscriptWord]:
    converted: list[TranscriptWord] = []
    for word in words:
        text = getattr(word, "word", "").strip()
        if not text:
            continue
        start = int(max(0.0, getattr(word, "start", 0.0)) * 1000)
        end = int(max(start, getattr(word, "end", start / 1000) * 1000))
        confidence = getattr(word, "probability", None)
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
        converted.append(
            TranscriptWord(
                word=text,
                start_ms=start,
                end_ms=end,
                confidence=confidence,
            )
        )
    return converted


def _transcribe_audio(
    *,
    audio_path: Path,
    language: str | None,
    prompt: str | None,
) -> list[TranscriptSegment]:
    model = _get_whisper_model()
    segments: list[TranscriptSegment] = []
    options: dict[str, object] = {"word_timestamps": True}
    if language:
        options["language"] = language
    if prompt:
        options["initial_prompt"] = prompt

    logger.debug(
        "worker.transcription.model_inference",
        model=model,
        language=language,
        prompt=bool(prompt),
    )
    results, _ = model.transcribe(str(audio_path), **options)
    for segment in results:
        start_ms = int(max(0.0, segment.start) * 1000)
        end_ms = int(max(segment.start, segment.end) * 1000)
        confidence = _confidence_from_logprob(getattr(segment, "avg_logprob", None))
        words = _convert_segment_words(getattr(segment, "words", []) or [])
        text = getattr(segment, "text", "").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=confidence,
                words=words or None,
            )
        )
    return segments


def _extract_audio(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stream = (
        ffmpeg.input(str(source))
        .output(str(destination), format="wav", ac=1, ar=16000)
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Audio extraction failed for transcription")
    return destination


@celery_app.task(name="transcription.process")
def transcription_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint that executes the transcription coroutine."""

    return asyncio.run(_transcription_process(UUID(job_id), UUID(org_id)))


async def _transcription_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.transcription.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for transcription")
            if job.video_id is None or job.transcript_id is None:
                raise RuntimeError("Transcription job missing video or transcript reference")

            transcript = await transcripts_repo.get(
                transcript_id=job.transcript_id, org_id=org_id
            )
            if transcript is None:
                raise RuntimeError("Transcript record missing for job")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None or not video.upload_key:
                raise RuntimeError("Video or source media missing for transcription")

            await transcripts_repo.update_transcription(
                transcript_id=transcript.id,
                org_id=org_id,
                status=TranscriptStatus.TRANSCRIBING,
                error=None,
            )

            with TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                source_path = storage.download_to_path(
                    video.upload_key, temp_dir_path / "source.mp4"
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.2,
                )
                audio_path = _extract_audio(source_path, temp_dir_path / "audio.wav")
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.45,
                )
                segments = _transcribe_audio(
                    audio_path=audio_path,
                    language=transcript.language_code,
                    prompt=transcript.prompt,
                )
                await transcripts_repo.update_transcription(
                    transcript_id=transcript.id,
                    org_id=org_id,
                    status=TranscriptStatus.COMPLETED,
                    segments=segments,
                    error=None,
                )

    except Exception as exc:
        logger.exception(
            "worker.transcription.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        async with _session_factory() as session:
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            job = await SqlAlchemyJobsRepository(session).get(job_id=job_id, org_id=org_id)
            if job and job.transcript_id:
                await transcripts_repo.update_transcription(
                    transcript_id=job.transcript_id,
                    org_id=org_id,
                    status=TranscriptStatus.FAILED,
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
    logger.info("worker.transcription.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

