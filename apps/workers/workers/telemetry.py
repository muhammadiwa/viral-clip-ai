"""Shared telemetry configuration for Celery workers."""

from __future__ import annotations

import threading
import time
from typing import Dict

from celery import Celery, signals
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram, start_http_server

from apps.api.app.core.config import get_settings

TASK_COUNTER = Counter(
    "viral_clip_celery_tasks_total",
    "Total Celery task executions grouped by status",
    labelnames=("task", "status"),
)
TASK_LATENCY = Histogram(
    "viral_clip_celery_task_duration_seconds",
    "Duration of completed Celery tasks",
    labelnames=("task",),
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

_start_times: Dict[str, float] = {}
_lock = threading.Lock()
_instrumented = False


def configure_worker_telemetry(app: Celery) -> None:
    """Instrument Celery with Prometheus counters and OpenTelemetry tracing."""

    global _instrumented
    if _instrumented:
        return

    settings = get_settings()

    if settings.worker_prometheus_port is not None:
        start_http_server(
            port=settings.worker_prometheus_port,
            addr=settings.worker_prometheus_host,
        )

    if settings.otel_exporter_otlp_endpoint:
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name or "viral-clip-workers",
                "service.namespace": "viral-clip",
                "service.version": "0.1.0",
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            headers=_parse_headers(settings.otel_exporter_otlp_headers),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        CeleryInstrumentor().instrument(tracer_provider=provider)
    else:
        CeleryInstrumentor().instrument()

    signals.task_prerun.connect(_handle_task_prerun, weak=False)
    signals.task_postrun.connect(_handle_task_postrun, weak=False)
    signals.task_failure.connect(_handle_task_failure, weak=False)

    _instrumented = True


def _handle_task_prerun(task_id: str, task, **_: object) -> None:
    with _lock:
        _start_times[task_id] = time.perf_counter()
    TASK_COUNTER.labels(task=task.name, status="started").inc()


def _handle_task_postrun(task_id: str, task, **_: object) -> None:
    duration = _pop_duration(task_id)
    TASK_COUNTER.labels(task=task.name, status="succeeded").inc()
    if duration is not None:
        TASK_LATENCY.labels(task=task.name).observe(duration)


def _handle_task_failure(task_id: str, exception, traceback, sender, **_: object) -> None:
    duration = _pop_duration(task_id)
    TASK_COUNTER.labels(task=sender.name if sender else "unknown", status="failed").inc()
    if duration is not None and sender is not None:
        TASK_LATENCY.labels(task=sender.name).observe(duration)


def _pop_duration(task_id: str) -> float | None:
    with _lock:
        start = _start_times.pop(task_id, None)
    if start is None:
        return None
    return max(0.0, time.perf_counter() - start)


def _parse_headers(raw: str | None) -> Dict[str, str]:
    if not raw:
        return {}
    headers: Dict[str, str] = {}
    for part in raw.split(","):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers
