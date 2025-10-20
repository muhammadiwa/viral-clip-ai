
# 30 — Backend Spec

**Services**
- api-gateway, ingest-worker, transcode-worker, asr-worker, nlp-worker, subtitle-worker, tts-worker, render-worker, retell-worker, export-worker, billing-worker.

**Clean Architecture**
- domain (entities), repositories (DB), services (use cases), adapters (engines), routers (I/O).

**API**
- Versioned REST `/v1/*`, JWT, idempotency, pagination, webhooks, WS/SSE.

**Adapters (Strategy Pattern)**
- `AsrEngine`, `TtsEngine`, `Embedder`, `SubtitleRenderer` with concrete impls (Whisper, Coqui, CLIP, libass).

### ✅ Progress
- SQLAlchemy-backed repositories now persist users, organizations, projects, videos, jobs, clips, transcripts, retells, artifacts, billing data, observability metrics, DMCA notices, webhooks, idempotency keys, and rate limits to Postgres with automatic table bootstrap on API startup.
- Idempotent POST responses, pagination helpers, and webhook fan-out operate against the same Postgres-backed repositories for consistent durability.
- Midtrans Snap/Core API integration powers subscription checkout, signature-verified webhooks, and environment-driven plan pricing without hardcoded secrets.
- Presigned MinIO uploads are exposed for direct video ingest to object storage while keeping API payloads lightweight.
- Celery task dispatch powers ingest, transcode, transcription, alignment, clip discovery, subtitle styling, TTS, export, and retell workers—each reporting status via `/jobs/{id}/worker-status`, persisting domain records, and uploading artifacts to MinIO.
- Workers enrich video metadata (duration, frame rate, resolution), attach scoring breakdowns to clips, honour brand-aware subtitle presets, mix dubbed audio with calibrated loudness, append intro/outro slates, watermark exports, and record billing usage counters automatically when jobs succeed.
- Shared heuristics modules expose the clip scoring, subtitle styling, mix profile, and watermark math so workers and the QA harness keep a single source of truth.
- Brand kits persist in Postgres with API CRUD routes, presigned asset uploads, and workers respect brand overrides while the UI provides management surfaces, project-level assignment, and brand-library curation.
- QA run summaries persist via the new repository and `/v1/observability/qa-runs` endpoints, the QA runner can publish `qa.*` metrics directly into the observability store, locale/genre/frame-diff coverage is stored for dashboard breakdowns, and findings capture linked artifact IDs, overlay metadata, assignee context, due dates, and multi-stage statuses while emitting webhook notifications when assignments or schedules shift.
- Job WebSocket streams now feed a toast notification system and waveform-enabled clip editor so operators receive instant feedback on pipeline success/failure states.
- Prometheus/OpenTelemetry instrumentation is wired for API and workers, and Kubernetes manifests document how to deploy the collector alongside database/cache/storage dependencies.

### ⚠️ Current limitations
- The regression QA harness enforces clip scoring, subtitle presets, audio mixing, and watermark placement, yet broader scenarios (long-form edits, additional locales, branded templates) plus automated diff/heatmap rendering and collaborative annotations still need to be captured to scale creative approvals.
- Observability automation (dashboards, alert routing, additional webhook topics) and production hardening (GPU scheduling, secrets templates, canary rollouts) remain to reach the architecture's long-term goals.
