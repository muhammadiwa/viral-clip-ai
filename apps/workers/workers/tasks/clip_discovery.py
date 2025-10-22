"""Celery task that discovers potential highlight clips using OpenCLIP."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from uuid import UUID

import cv2
import ffmpeg
import numpy as np
import open_clip
import structlog
import torch
from PIL import Image
from scipy.io import wavfile

from apps.api.app.core.config import get_settings
from apps.api.app.db.session import get_sessionmaker
from apps.api.app.domain.artifacts import ArtifactCreate, ArtifactKind
from apps.api.app.domain.clips import ClipCreate
from apps.api.app.domain.billing import UsageIncrementRequest
from apps.api.app.domain.jobs import JobStatus
from apps.api.app.domain.transcripts import TranscriptSegment
from apps.api.app.repositories.artifacts import SqlAlchemyArtifactsRepository
from apps.api.app.repositories.billing import SqlAlchemyBillingRepository
from apps.api.app.repositories.clips import SqlAlchemyClipsRepository
from apps.api.app.repositories.jobs import SqlAlchemyJobsRepository
from apps.api.app.repositories.transcripts import SqlAlchemyTranscriptsRepository
from apps.api.app.repositories.videos import SqlAlchemyVideosRepository
from apps.api.app.services.storage import MinioStorageService, build_storage_service
from apps.workers.workers.heuristics.clip import compute_candidate_confidence

from .shared import update_job_status
from ..start import celery_app

logger = structlog.get_logger(__name__)

_session_factory = get_sessionmaker()
_storage: MinioStorageService | None = None
_clip_model: torch.nn.Module | None = None
_clip_preprocess: callable | None = None


@dataclass
class _SampledFrame:
    timestamp_ms: int
    image: Image.Image


def _get_storage() -> MinioStorageService:
    global _storage
    if _storage is None:
        _storage = build_storage_service()
    return _storage


def _get_clip_model() -> tuple[torch.nn.Module, callable]:
    global _clip_model, _clip_preprocess
    if _clip_model is None or _clip_preprocess is None:
        settings = get_settings()
        model, preprocess, _ = open_clip.create_model_and_transforms(
            settings.clip_model_name,
            pretrained=settings.clip_model_pretrained,
        )
        model.eval()
        if torch.cuda.is_available():
            model = model.to("cuda")
        _clip_model = model
        _clip_preprocess = preprocess
    return _clip_model, _clip_preprocess


def _sample_frames(video_path: Path, interval_seconds: int) -> list[_SampledFrame]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("Unable to open video for clip discovery")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_step = max(int(fps * interval_seconds), 1)

    samples: list[_SampledFrame] = []
    frame_index = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        if frame_index % frame_step == 0:
            timestamp_ms = int((frame_index / fps) * 1000)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            samples.append(_SampledFrame(timestamp_ms=timestamp_ms, image=image))
        frame_index += 1

    capture.release()
    return samples


def _frame_embeddings(samples: Iterable[_SampledFrame]) -> tuple[np.ndarray, list[_SampledFrame]]:
    model, preprocess = _get_clip_model()
    device = next(model.parameters()).device

    embeddings: list[np.ndarray] = []
    retained: list[_SampledFrame] = []
    for sample in samples:
        tensor = preprocess(sample.image).unsqueeze(0)
        tensor = tensor.to(device)
        with torch.no_grad():
            embed = model.encode_image(tensor)
        vector = embed[0].detach().cpu().numpy()
        norm = np.linalg.norm(vector)
        if norm == 0:
            continue
        embeddings.append(vector / norm)
        retained.append(sample)
    if not embeddings:
        raise RuntimeError("Unable to compute CLIP embeddings for video")
    return np.vstack(embeddings), retained


def _extract_audio_waveform(source: Path, destination: Path) -> tuple[np.ndarray, int]:
    """Return a normalised mono waveform for downstream scoring."""

    stream = (
        ffmpeg.input(str(source))
        .output(str(destination), format="wav", ac=1, ar=16000)
        .overwrite_output()
    )
    stream.run(capture_stdout=True, capture_stderr=True)
    sample_rate, samples = wavfile.read(destination)
    if samples.ndim > 1:
        samples = samples[:, 0]
    if samples.dtype == np.int16:
        normalised = samples.astype(np.float32) / 32768.0
    elif samples.dtype == np.int32:
        normalised = samples.astype(np.float32) / 2147483648.0
    else:
        normalised = samples.astype(np.float32)
    max_val = float(np.max(np.abs(normalised))) if normalised.size else 0.0
    if max_val > 0:
        normalised = normalised / max_val
    return normalised, int(sample_rate)


def _segment_energy(samples: np.ndarray, sample_rate: int, start_ms: int, end_ms: int) -> float:
    if samples.size == 0 or sample_rate <= 0:
        return 0.0
    start_index = max(0, int(start_ms / 1000.0 * sample_rate))
    end_index = min(samples.size, int(end_ms / 1000.0 * sample_rate))
    if end_index <= start_index:
        return 0.0
    window = samples[start_index:end_index]
    return float(np.sqrt(np.mean(np.square(window))))


def _keyword_density(segments: list[TranscriptSegment], start_ms: int, end_ms: int) -> float:
    window = max(1, end_ms - start_ms)
    emphasis = 0.0
    for segment in segments:
        overlap = min(segment.end_ms, end_ms) - max(segment.start_ms, start_ms)
        if overlap <= 0:
            continue
        confidence = segment.confidence if segment.confidence is not None else 0.7
        if confidence < 0.35:
            continue
        emphasis += overlap * confidence
    return max(0.0, min(1.0, emphasis / window))


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _apply_duration_constraints(
    start_ms: int,
    end_ms: int,
    *,
    video_duration_ms: int | None,
    min_duration_ms: int,
    max_duration_ms: int,
) -> tuple[int, int, int]:
    """Return a bounded window respecting duration and video limits."""

    start = max(0, start_ms)
    end = max(start + 1, end_ms)
    duration = end - start

    if duration < min_duration_ms:
        padding = min_duration_ms - duration
        start = max(0, start - padding // 2)
        end = start + min_duration_ms
    elif duration > max_duration_ms:
        end = start + max_duration_ms

    if video_duration_ms is not None and end > video_duration_ms:
        shift = end - video_duration_ms
        start = max(0, start - shift)
        end = min(video_duration_ms, start + max_duration_ms)
    duration = end - start
    return start, end, duration


def _discover_candidate_windows(
    embeddings: np.ndarray,
    samples: list[_SampledFrame],
    *,
    max_clips: int,
) -> list[tuple[int, int, float, _SampledFrame]]:
    if embeddings.shape[0] < 2:
        only = samples[0]
        return [(max(0, only.timestamp_ms - 5000), only.timestamp_ms + 10000, 1.0, only)]

    deltas = np.linalg.norm(np.diff(embeddings, axis=0), axis=1)
    if np.allclose(deltas, 0):
        deltas = np.ones_like(deltas)
    ranking = np.argsort(deltas)[::-1][: max(max_clips * 3, max_clips)]
    max_delta = float(deltas[ranking[0]]) if ranking.size > 0 else 1.0
    candidates: list[tuple[int, int, float, _SampledFrame]] = []
    for index in sorted(ranking):
        raw_strength = float(deltas[index])
        strength = raw_strength / max_delta if max_delta else 1.0
        anchor = samples[min(index + 1, len(samples) - 1)]
        start_ms = max(0, anchor.timestamp_ms - 7500)
        end_ms = anchor.timestamp_ms + 15000
        candidates.append((start_ms, end_ms, strength, anchor))
    return candidates


@celery_app.task(name="clips.discover")
def clip_discovery_process(*, job_id: str, org_id: str, max_clips: int = 5) -> dict:
    """Celery entrypoint that bridges into the async discovery coroutine."""

    return asyncio.run(
        _clip_discovery_process(UUID(job_id), UUID(org_id), max_clips=max_clips)
    )


async def _clip_discovery_process(
    job_id: UUID, org_id: UUID, *, max_clips: int
) -> dict:
    logger.info("worker.clip_discovery.start", job_id=str(job_id), org_id=str(org_id))
    await update_job_status(
        org_id=org_id, job_id=job_id, status=JobStatus.RUNNING, progress=0.05
    )
    storage = _get_storage()

    generated_clips: list = []
    sampled_frames: list[_SampledFrame] = []

    try:
        async with _session_factory() as session:
            jobs_repo = SqlAlchemyJobsRepository(session)
            videos_repo = SqlAlchemyVideosRepository(session)
            clips_repo = SqlAlchemyClipsRepository(session)
            transcripts_repo = SqlAlchemyTranscriptsRepository(session)
            artifacts_repo = SqlAlchemyArtifactsRepository(session)
            billing_repo = SqlAlchemyBillingRepository(session)

            job = await jobs_repo.get(job_id=job_id, org_id=org_id)
            if job is None:
                raise RuntimeError("Job record not found for clip discovery")
            if job.video_id is None:
                raise RuntimeError("Clip discovery job missing video reference")

            video = await videos_repo.get(video_id=job.video_id, org_id=org_id)
            if video is None or not video.upload_key:
                raise RuntimeError("Video or source media missing for clip discovery")

            settings = get_settings()
            transcripts = await transcripts_repo.list_for_video(
                video_id=video.id, org_id=org_id
            )
            transcript_segments: list[TranscriptSegment] = []
            for transcript in transcripts:
                transcript_segments.extend(
                    transcript.aligned_segments or transcript.segments
                )
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                source = storage.download_to_path(
                    video.upload_key, temp_path / "source.mp4"
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.2,
                )
                sampled_frames = _sample_frames(
                    source, settings.clip_sample_interval_seconds
                )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.35,
                )
                embeddings, retained = _frame_embeddings(sampled_frames)
                sampled_frames = retained
                try:
                    audio_waveform, audio_rate = _extract_audio_waveform(
                        source, temp_path / "waveform.wav"
                    )
                except Exception as exc:  # pragma: no cover - auxiliary path
                    audio_waveform = np.array([])
                    audio_rate = 0
                    logger.warning(
                        "worker.clip_discovery.audio_failed",
                        job_id=str(job_id),
                        org_id=str(org_id),
                        error=str(exc),
                    )
                await update_job_status(
                    org_id=org_id,
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.55,
                )
                candidates = _discover_candidate_windows(
                    embeddings, sampled_frames, max_clips=max_clips
                )

                energies: list[float] = []
                keyword_scores: list[float] = []
                for start, end, _, _ in candidates:
                    energies.append(
                        _segment_energy(audio_waveform, audio_rate, start, end)
                    )
                    keyword_scores.append(
                        _keyword_density(transcript_segments, start, end)
                    )

                peak_energy = max(energies, default=0.0)
                min_duration_ms = settings.clip_min_duration_seconds * 1000
                max_duration_ms = settings.clip_max_duration_seconds * 1000
                target_duration_ms = settings.clip_target_duration_seconds * 1000
                weight_motion = max(settings.clip_motion_weight, 0.0)
                weight_audio = max(settings.clip_audio_weight, 0.0)
                weight_keywords = max(settings.clip_keyword_weight, 0.0)
                weight_duration = max(settings.clip_duration_weight, 0.0)
                bias = settings.clip_confidence_bias
                threshold = settings.clip_confidence_threshold

                scored_candidates: list[dict[str, object]] = []
                for candidate, energy, keyword in zip(
                    candidates, energies, keyword_scores
                ):
                    start, end, strength, anchor = candidate
                    bounded_start, bounded_end, duration = _apply_duration_constraints(
                        start,
                        end,
                        video_duration_ms=video.duration_ms,
                        min_duration_ms=min_duration_ms,
                        max_duration_ms=max_duration_ms,
                    )
                    confidence, components = compute_candidate_confidence(
                        motion_strength=strength,
                        audio_energy=energy,
                        peak_energy=peak_energy,
                        keyword_score=keyword,
                        duration_ms=duration,
                        target_duration_ms=target_duration_ms,
                        weight_motion=weight_motion,
                        weight_audio=weight_audio,
                        weight_keywords=weight_keywords,
                        weight_duration=weight_duration,
                        bias=bias,
                    )
                    if confidence < threshold:
                        continue
                    scored_candidates.append(
                        {
                            "start": bounded_start,
                            "end": bounded_end,
                            "anchor": anchor,
                            "confidence": confidence,
                            "components": {
                                key: round(value, 3)
                                for key, value in components.items()
                            },
                            "duration": duration,
                        }
                    )

                scored_candidates.sort(
                    key=lambda payload: float(payload["confidence"]), reverse=True
                )

                selected: list[dict[str, object]] = []
                for candidate in scored_candidates:
                    if len(selected) >= max_clips:
                        break
                    if any(
                        abs(int(candidate["start"]) - int(existing["start"]))
                        < min_duration_ms // 2
                        for existing in selected
                    ):
                        continue
                    selected.append(candidate)

                clip_payloads: list[ClipCreate] = []
                preview_sources: list[dict[str, object]] = []
                for index, candidate in enumerate(selected, start=1):
                    clip_payloads.append(
                        ClipCreate(
                            start_ms=int(candidate["start"]),
                            end_ms=int(candidate["end"]),
                            title=f"Highlight {index}",
                            description="High energy moment scored across motion, audio, script, and pacing cues",
                            confidence=float(candidate["confidence"]),
                            score_components=candidate["components"],
                        )
                    )
                    preview_sources.append(candidate)

                clips = await clips_repo.replace_for_video(
                    org_id=org_id,
                    project_id=video.project_id,
                    video_id=video.id,
                    clips=clip_payloads,
                )
                generated_clips = clips

                preview_storage_bytes = 0
                for clip, candidate in zip(clips, preview_sources):
                    anchor = candidate["anchor"]
                    preview_path = temp_path / f"clip-{clip.id}.jpg"
                    anchor.image.save(preview_path, format="JPEG", quality=90)
                    object_key = storage.generate_object_key(
                        org_id=org_id,
                        project_id=video.project_id,
                        suffix="clip-preview",
                    )
                    storage.upload_file(
                        object_key,
                        preview_path,
                        content_type="image/jpeg",
                    )
                    preview_storage_bytes += preview_path.stat().st_size
                    await artifacts_repo.create(
                        org_id=org_id,
                        payload=ArtifactCreate(
                            project_id=video.project_id,
                            video_id=video.id,
                            clip_id=clip.id,
                            kind=ArtifactKind.CLIP_PREVIEW,
                            uri=storage.object_uri(object_key),
                            content_type="image/jpeg",
                        ),
                    )

                await billing_repo.record_usage(
                    org_id,
                    UsageIncrementRequest(
                        clips_generated=len(clips),
                        storage_gb=preview_storage_bytes / (1024**3),
                    ),
                )

    except Exception as exc:
        logger.exception(
            "worker.clip_discovery.failed",
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
    logger.info(
        "worker.clip_discovery.complete",
        job_id=str(job_id),
        org_id=str(org_id),
        clips=len(generated_clips),
    )
    return {"job_id": str(job_id), "org_id": str(org_id), "clips": len(generated_clips)}

