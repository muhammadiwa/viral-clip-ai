
# 10 — Roadmap (Beyond MVP)
<same content as in the single-file doc, split for clarity>

## Phase 0 — Foundations
- Repos, CI, lint/test; Dockerfiles; shared schemas.
- MinIO + Postgres + Redis baseline; API skeleton; auth; presigned upload; UI shell.
**Done when:** Login + upload + list asset.

### ✅ Progress
- API skeleton online with organization-aware project CRUD (create/list/read).
- Video ingest endpoint returns pending job resource for existing projects.
- Job orchestration endpoints expose ingest/transcode queueing and project job listings.
- Worker-facing job updates synchronize video lifecycle states across ingest and transcode.
- Project video listings and detail endpoints expose pipeline status for UI surfaces.
- Clip discovery requests enqueue analysis jobs and expose generated clip listings per video.
- Subtitle styling requests enqueue render jobs and track clip styling status for review.
- TTS dubbing requests enqueue voice-over synthesis jobs and report narration progress on clips.
- Project export requests enqueue final render jobs while tracking export lifecycle states.
- Job WebSocket streams broadcast real-time job updates to connected clients.
- Job control endpoints allow pausing, resuming, cancelling, and retrying pipeline jobs with side effects propagated to linked resources.
- Audit logging captures job control actions for compliance and troubleshooting visibility.
- DMCA notice endpoints capture takedown submissions and review outcomes for compliance workflows.
- Rate limiting enforces per-member quotas on high-impact API actions to prevent abuse.
- Idempotency key storage enables safe retries for POST operations across pipeline and compliance APIs.
- Standardized limit/offset pagination powers consistent tables across all collection endpoints.
- Movie retell requests enqueue narrative synthesis jobs and expose the latest retell session per project.
- Movie retell detail updates persist generated summaries and outlines for downstream consumption.
- Transcription and alignment endpoints orchestrate ASR outputs and advance videos toward clip discovery.
- Artifact registration endpoints capture generated media across projects, videos, and clips for download surfaces.
- Billing subscription and usage endpoints expose plan management and quota tracking for each organization, with Midtrans-backed checkout flows to activate paid plans and auto-align subscription state on settlement.
- User and organization management endpoints establish multi-tenant workspaces with role-aware memberships.
- SQLAlchemy persistence now backs users, organizations, and memberships so identity data survives API restarts.
- Projects, videos, and jobs now persist to Postgres via SQLAlchemy, keeping core pipeline state durable across API restarts.
- Clips, transcripts, retells, artifacts, billing, observability, DMCA, idempotency, webhooks, and rate limiting now persist to Postgres as well, eliminating the prior in-memory gaps.
- Video ingest returns presigned MinIO upload credentials when needed so the UI can stream large files directly to object storage.
- Authentication endpoints issue JWT tokens and expose the current-user context for session bootstrap.
- Role-based access control enforces active organization membership and role checks across pipeline endpoints.
- Observability metrics endpoints record pipeline timings and evaluate job completion SLO health for dashboards.
- Webhook endpoint management captures outbound subscriptions and delivery logs for external integrations.
- Celery-backed ingest and transcode workers now validate uploads, pull remote sources, emit HLS previews, and register generated artifacts in MinIO while updating job state through the API.
- Transcription, alignment, clip discovery, subtitle styling, TTS dubbing, export, and retell Celery workers execute the full media pipeline, persisting transcripts, clips, audio, and final renders back to MinIO and Postgres.
- The React dashboard now ships inline transcript and clip editors, media artifact previews, and subscription/usage visualizations that react to job streaming updates in real time.
- Clip discovery now blends motion deltas, audio energy, transcript keyword coverage, and duration targets when ranking highlights, storing confidence breakdowns for editors and enriching video metadata with duration/frame-rate details.
- Subtitle styling supports reusable presets (bold, clean, karaoke) with environment-driven brand overrides, while the dubbing worker mixes synthesized narration against the original bed using configurable loudness targets and registers both stems for review.
- Project exports append configured intro/outro slates, apply watermark overlays, upload the branded render to MinIO, and report the processed minutes back to billing for quota accuracy.
- Workers now report minutes processed, clips generated, retells created, and storage consumption straight to the billing repository when jobs succeed, keeping usage dashboards accurate without manual reporting.
- A dataset-driven QA harness exercises clip scoring, subtitle presets, TTS mixing, and watermark placement to keep media heuristics within calibrated ranges during regression runs.
- The QA dataset now covers multilingual highlights and narrative cases, records qa.* observability metrics, persists run summaries for creative review, and surfaces the latest results directly in the dashboard.
- QA findings now carry overlay links/metadata and assignee context, while the API enforces active-member assignments and the dashboard exposes inline ownership controls for each regression.
- QA assignment workflows now include due dates, expanded status transitions (in progress, blocked, ready for review), and webhook notifications when ownership or schedules change.
- Brand kits persist in Postgres with API CRUD support, and the dashboard exposes management tools plus project-level selectors so exports inherit the correct presets.
- Clip editors now surface waveform timelines, preview scrubbing, and inline metadata edits while toast notifications announce job success/failure via the job event stream.
- Brand libraries support MinIO-presigned asset uploads (watermarks, logos, fonts, slates) with dashboard previews and delete flows so creative teams maintain production-ready kits in-app.
- The clip editor now lets operators select transcript-backed segments, split or merge timelines, snap clip bounds to segment limits, and preview waveforms for precise trims.
- QA regression reports include locale/genre coverage maps and frame-diff counts, and the dashboard exposes the breakdown alongside reviewer notes for faster creative sign-off.
- Prometheus and OpenTelemetry instrumentation is wired across the API and workers, enabling external scraping through the bundled collector manifests.
- GitHub Actions CI compiles API/workers/UI, runs the QA baseline, executes an API smoke test, and the Kubernetes manifests cover Postgres, Redis, MinIO, API deployments, Celery workers, and OTLP collection.

### ⚠️ Outstanding gaps
- Extend the QA library with automated golden-frame diffs, annotation workflows, and expanded fixtures so creative approvals scale beyond the current overlay-guided checks.
- Extend the editorial workspace with timeline ripple edits, keyboard shortcuts, retell script editing, and brand-kit asset versioning to satisfy the full UX brief.
- Automate observability with published Prometheus rules, Grafana dashboards, alert routing, and richer webhook events (e.g., `clip.styled`, `export.completed`).
- Harden infrastructure with GPU-aware scheduling, secrets management templates, canary rollouts, and cost monitoring layered atop the new Kubernetes manifests and CI pipeline.

### 🔜 Phase Execution Plan
1. Layer in advanced editorial tooling (timeline ripple edits, keyboard shortcuts, retell script editor, quota warnings) and integrate brand-kit asset versioning with export workflows.
2. Publish observability automation (Prometheus alert rules, Grafana dashboards, webhook catalogue) and wire coverage/QA metrics into executive reporting.
3. Finalise production infrastructure (GPU node pools, secrets management templates, canary rollouts, smoke-test gates) to make the Kubernetes deployment production ready.

## Phase 1 — Ingest & Transcode
- `yt-dlp`, tus/multipart uploads; FFmpeg HLS mezz + player preview.
**Done when:** Play HLS, job progress visible.

## Phase 2 — ASR + Alignment
- faster-whisper; WhisperX; word timestamps; SRT/VTT.
**Done when:** Accurate subs editable on timeline.

## Phase 3 — Clip Discovery
- Scene detect; CLIP embeddings; ranking; candidate clips + export MP4.
**Done when:** Top‑N clips playable and saved.

## Phase 4 — Subtitle Styles & Templates
- ASS styles; overlay renderer; brand kits; watermark; intro/outro.
**Done when:** Styled subs match export pixel‑perfect.

## Phase 5 — TTS / Dubbing
- Coqui/Piper; multi‑lang; volume ducking; batch synthesis.
**Done when:** Clip exported with dubbed narration.

## Phase 6 — Movie Retell
- LLM chapters + narration; scene re‑assembly; <1h export.
**Done when:** Coherent retell delivered.

## Phase 7 — SaaS Hardening
- Plans, metering, limits; billing; RBAC; audit; admin dashboards.
**Done when:** Limits enforced; upgrade unlocks promptly.

## Phase 8 — Scale & Polish
- GPU autoscale; CDN; A/B subtitle presets; template marketplace.
**Done when:** SLOs hit at target load.
