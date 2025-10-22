"""Utilities shared across Celery tasks."""

from __future__ import annotations

from uuid import UUID

import httpx
import structlog

from apps.api.app.core.config import get_settings
from apps.api.app.domain.jobs import JobStatus

logger = structlog.get_logger(__name__)


async def update_job_status(
    *,
    org_id: UUID,
    job_id: UUID,
    status: JobStatus,
    progress: float | None = None,
    message: str | None = None,
) -> dict:
    """Call back into the API to update a job status with side effects."""

    settings = get_settings()
    if not settings.api_base_url:
        raise RuntimeError("API_BASE_URL is not configured for worker callbacks")
    if not settings.worker_service_token:
        raise RuntimeError("WORKER_SERVICE_TOKEN is not configured")

    payload: dict[str, object] = {"status": status.value}
    if progress is not None:
        payload["progress"] = progress
    if message is not None:
        payload["message"] = message

    url = f"{str(settings.api_base_url).rstrip('/')}{settings.api_v1_prefix}/jobs/{job_id}/worker-status"
    headers = {
        "X-Org-ID": str(org_id),
        "X-Worker-Token": settings.worker_service_token,
        "Content-Type": "application/json",
    }

    logger.debug(
        "worker.job_update.request",
        url=url,
        job_id=str(job_id),
        org_id=str(org_id),
        status=status.value,
        progress=progress,
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.patch(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.debug(
            "worker.job_update.response",
            job_id=str(job_id),
            org_id=str(org_id),
            status=status.value,
        )
        return data
