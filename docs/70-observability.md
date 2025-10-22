
# 70 — Observability & SLOs
Metrics: latency per step, GPU/CPU util, error rates; 95p job-complete SLO; dashboards and alerts.

### ✅ Progress
- Metrics endpoints capture pipeline timings and expose rollups plus SLO evaluations for dashboards.
- QA regression runs post qa.* metrics and structured summaries, allowing dashboards to track clip/subtitle/mix/watermark pass rates, locale/genre coverage, frame-diff failures, and linked artifact IDs alongside pipeline latency.
- FastAPI and Celery are instrumented with Prometheus/OpenTelemetry exporters, and the Kubernetes manifests ship an OTLP collector + Prometheus endpoint to aggregate traces/metrics out of the box.
