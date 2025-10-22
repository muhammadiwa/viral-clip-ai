"""Celery task dispatch helpers for background pipeline processing."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from celery import Celery

from ..core.config import get_settings


class TaskQueueConfigurationError(RuntimeError):
    """Raised when Celery cannot be configured from the environment."""


@dataclass
class TaskDispatcher:
    """Thin wrapper that fires Celery tasks for pipeline jobs."""

    app: Celery

    def enqueue_ingest(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the ingest worker for the provided job."""

        self._send_task("ingest.process", job_id=job_id, org_id=org_id)

    def enqueue_transcode(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the transcode worker for the provided job."""

        self._send_task("transcode.process", job_id=job_id, org_id=org_id)

    def enqueue_transcription(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the transcription worker."""

        self._send_task("transcription.process", job_id=job_id, org_id=org_id)

    def enqueue_alignment(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the alignment worker."""

        self._send_task("alignment.process", job_id=job_id, org_id=org_id)

    def enqueue_clip_discovery(
        self, *, job_id: UUID, org_id: UUID, max_clips: int
    ) -> None:
        """Queue the clip discovery worker with the requested clip count."""

        self._send_task(
            "clips.discover",
            job_id=job_id,
            org_id=org_id,
            extra_kwargs={"max_clips": max_clips},
        )

    def enqueue_subtitle_render(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the subtitle styling worker."""

        self._send_task("clips.subtitle_render", job_id=job_id, org_id=org_id)

    def enqueue_tts(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the clip TTS worker."""

        self._send_task("clips.tts", job_id=job_id, org_id=org_id)

    def enqueue_retell(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the movie retell synthesis worker."""

        self._send_task("retell.generate", job_id=job_id, org_id=org_id)

    def enqueue_project_export(self, *, job_id: UUID, org_id: UUID) -> None:
        """Queue the final project export renderer."""

        self._send_task("projects.export", job_id=job_id, org_id=org_id)

    def _send_task(
        self,
        name: str,
        *,
        job_id: UUID,
        org_id: UUID,
        extra_kwargs: dict[str, object] | None = None,
    ) -> None:
        payload = {"job_id": str(job_id), "org_id": str(org_id)}
        if extra_kwargs:
            payload.update(extra_kwargs)
        self.app.send_task(
            name,
            kwargs=payload,
            ignore_result=True,
        )


def build_task_dispatcher() -> TaskDispatcher:
    """Create a dispatcher backed by a configured Celery app."""

    settings = get_settings()
    broker = settings.celery_broker_url or settings.redis_url
    if not broker:
        raise TaskQueueConfigurationError(
            "CELERY_BROKER_URL or REDIS_URL must be configured for task dispatch"
        )
    backend = settings.celery_result_backend or broker
    app = Celery("viral_clip_api", broker=broker, backend=backend)
    app.conf.update(
        task_default_queue="default",
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
    )
    return TaskDispatcher(app=app)
