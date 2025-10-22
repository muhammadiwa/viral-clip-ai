"""Celery task that performs word-level alignment using WhisperX."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import ffmpeg
import structlog
import torch
import whisperx

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.domain.transcripts import (
    AlignmentStatus,
    TranscriptSegment,
    TranscriptWord,
)
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service

from .shared import update_job_status
from ..start import celery_app

logger = structlog.get_logger(__name__)

_session_factory = get_sessionmaker()
_storage: MinioStorageService | None = None
_alignment_cache: dict[tuple[str, str], tuple[object, dict]] = {}


def _get_storage() -> MinioStorageService:
    global _storage
    if _storage is None:
        _storage = build_storage_service()
    return _storage


def _normalise_language(language: str | None) -> str:
    if not language:
        return "en"
    return language.split("-")[0].lower()


def _alignment_device(settings) -> str:
    if settings.alignment_device:
        return settings.alignment_device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_alignment_model(language: str) -> tuple[object, dict, str]:
    settings = get_settings()
    device = _alignment_device(settings)
    cache_key = (language, device)
    if cache_key not in _alignment_cache:
        model, metadata = whisperx.load_align_model(
            language_code=language,
            device=device,
            model_name=settings.alignment_model_name,
        )
        _alignment_cache[cache_key] = (model, metadata)
    model, metadata = _alignment_cache[cache_key]
    return model, metadata, device


def _extract_audio(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stream = (
        ffmpeg.input(str(source))
        .output(str(destination), format="wav", ac=1, ar=16000)
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    if not destination.exists():
        raise RuntimeError("Audio extraction failed for alignment")
    return destination


def _align_segments(
    *,
    language: str,
    audio_path: Path,
    base_segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    model, metadata, device = _get_alignment_model(language)
    logger.debug(
        "worker.alignment.model_loaded",
        language=language,
        device=device,
    )
    whisper_segments = [
        {
            "id": index,
            "text": segment.text,
            "start": segment.start_ms / 1000.0,
            "end": segment.end_ms / 1000.0,
        }
        for index, segment in enumerate(base_segments)
    ]
    if not whisper_segments:
        return []

    alignment_result = whisperx.align(
        whisper_segments,
        model,
        metadata,
        str(audio_path),
        device,
        return_char_alignments=False,
    )
    word_segments = alignment_result.get("word_segments", [])
    grouped: dict[int, list[TranscriptWord]] = defaultdict(list)
    for word in word_segments:
        text = (word.get("text") or "").strip()
        if not text:
            continue
        start = int(max(0.0, float(word.get("start", 0.0))) * 1000)
        end = int(max(start, float(word.get("end", 0.0))) * 1000)
        confidence = word.get("confidence")
        if confidence is not None:
            confidence = max(0.0, min(1.0, float(confidence)))
        segment_index = int(word.get("segment", 0))
        grouped[segment_index].append(
            TranscriptWord(
                word=text,
                start_ms=start,
                end_ms=end,
                confidence=confidence,
            )
        )

    aligned_segments: list[TranscriptSegment] = []
    for index, base in enumerate(base_segments):
        words = grouped.get(index) or None
        aligned_segments.append(
            TranscriptSegment(
                start_ms=base.start_ms,
                end_ms=base.end_ms,
                text=base.text,
                confidence=base.confidence,
                words=words,
            )
        )
    return aligned_segments


@celery_app.task(name="alignment.process")
def alignment_process(*, job_id: str, org_id: str) -> dict:
    """Celery entrypoint for WhisperX alignment."""

    return asyncio.run(_alignment_process(UUID(job_id), UUID(org_id)))


async def _alignment_process(job_id: UUID, org_id: UUID) -> dict:
    logger.info("worker.alignment.start", job_id=str(job_id), org_id=str(org_id))
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
                raise RuntimeError("Job record not found for alignment")
            if job.video_id is None or job.transcript_id is None:
                raise RuntimeError("Alignment job missing references")

            transcript = await transcripts_repo.get(
                transcript_id=job.transcript_id, org_id=org_id
            )
            if transcript is None:
                raise RuntimeError("Transcript not found for alignment job")
            if not transcript.segments:
                raise RuntimeError("Transcript must contain segments before alignment")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None or not video.upload_key:
                raise RuntimeError("Video media missing for alignment")

            await transcripts_repo.update_alignment(
                transcript_id=transcript.id,
                org_id=org_id,
                status=AlignmentStatus.ALIGNING,
                error=None,
            )

            language = _normalise_language(transcript.language_code)

            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                source = storage.download_to_path(
                    video.upload_key, temp_path / "source.mp4"
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.25,
                )
                audio = _extract_audio(source, temp_path / "audio.wav")
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.45,
                )
                aligned_segments = _align_segments(
                    language=language,
                    audio_path=audio,
                    base_segments=transcript.segments,
                )
                await transcripts_repo.update_alignment(
                    transcript_id=transcript.id,
                    org_id=org_id,
                    status=AlignmentStatus.ALIGNED,
                    segments=aligned_segments,
                    error=None,
                )

    except Exception as exc:
        logger.exception(
            "worker.alignment.failed",
            job_id=str(job_id),
            org_id=str(org_id),
            error=str(exc),
        )
        async with _session_factory() as session:
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            job = await SqlAlchemyJobsRepository(session).get(job_id=job_id, org_id=org_id)
            if job and job.transcript_id:
                await transcripts_repo.update_alignment(
                    transcript_id=job.transcript_id,
                    org_id=org_id,
                    status=AlignmentStatus.FAILED,
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
    logger.info("worker.alignment.complete", job_id=str(job_id), org_id=str(org_id))
    return {"job_id": str(job_id), "org_id": str(org_id)}

