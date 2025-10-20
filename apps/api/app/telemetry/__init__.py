"""Telemetry helpers for exposing Prometheus metrics and OpenTelemetry traces."""

from __future__ import annotations

import re
import time
from typing import Dict

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..core.config import get_settings

REQUEST_COUNT = Counter(
    "viral_clip_http_requests_total",
    "Total count of HTTP requests",
    labelnames=("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "viral_clip_http_request_duration_seconds",
    "Latency distribution for HTTP requests",
    labelnames=("method", "path"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

_uuid_pattern = re.compile(r"/[0-9a-fA-F-]{32,36}")
_numeric_pattern = re.compile(r"/\d+")
_tracing_configured = False


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request metrics for Prometheus scraping."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = _normalise_path(request.url.path)
        if path.startswith("/metrics"):
            return response
        REQUEST_COUNT.labels(
            method=request.method, path=path, status=str(response.status_code)
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        return response


def setup_prometheus(app: FastAPI) -> None:
    """Attach middleware and metrics endpoint."""

    app.add_middleware(PrometheusMiddleware)

    @app.get(get_settings().prometheus_metrics_path, include_in_schema=False)
    async def prometheus_metrics() -> Response:  # pragma: no cover - trivial
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def configure_tracing(app: FastAPI) -> None:
    """Configure OpenTelemetry exporters when enabled via settings."""

    global _tracing_configured
    settings = get_settings()
    if not settings.otel_exporter_otlp_endpoint:
        return
    if _tracing_configured:
        FastAPIInstrumentor.instrument_app(app)
        return

    headers = _parse_headers(settings.otel_exporter_otlp_headers)
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name or settings.project_name,
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=headers,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    _tracing_configured = True


def _normalise_path(path: str) -> str:
    path = _uuid_pattern.sub("/{uuid}", path)
    path = _numeric_pattern.sub("/{id}", path)
    if not path:
        return "/"
    return path


def _parse_headers(raw: str | None) -> Dict[str, str]:
    if not raw:
        return {}
    headers: Dict[str, str] = {}
    for part in raw.split(","):
        if not part:
            continue
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers
