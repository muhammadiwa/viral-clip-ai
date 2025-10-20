# 12 — Implementation Gap Analysis

## Current State Verification
The following subsystems were reviewed against the committed codebase to confirm that they execute real behavior instead of placeholders:

| Area | Implementation evidence |
| --- | --- |
| **Identity & Auth** | Users, organizations, and memberships persist via SQLAlchemy ORM models and repositories, with JWT issuance and bcrypt password hashing handled in the auth router. 【F:apps/api/app/models/user.py†L1-L28】【F:apps/api/app/api/routes/auth.py†L1-L159】 |
| **Projects & Videos** | Project/video entities, repositories, and REST handlers read/write Postgres. Video ingest provides presigned MinIO credentials and creates ingest jobs. 【F:apps/api/app/repositories/projects.py†L1-L171】【F:apps/api/app/api/routes/videos.py†L1-L214】 |
| **Object Storage** | `MinioStorageService` performs real MinIO CRUD plus presigned upload URL generation, and worker tasks consume it during ingest/transcode. 【F:apps/api/app/services/storage.py†L1-L129】【F:apps/workers/workers/tasks/transcode.py†L1-L135】 |
| **Job Orchestration** | Jobs persist in Postgres, expose lifecycle endpoints, and worker callbacks hit `/worker-status` using authenticated tokens. 【F:apps/api/app/repositories/jobs.py†L1-L180】【F:apps/api/app/api/routes/jobs.py†L1-L377】 |
| **Ingest Worker** | Celery task validates uploaded objects or downloads YouTube videos via `yt-dlp`, pushing verified sources into MinIO and reporting progress back to the API. 【F:apps/workers/workers/tasks/ingest.py†L1-L140】 |
| **Transcode Worker** | Celery task materializes HLS renditions with FFmpeg, uploads playlist/segments to MinIO, registers artifacts, and advances job state. 【F:apps/workers/workers/tasks/transcode.py†L1-L153】 |
| **ASR & Alignment** | Celery workers use faster-whisper and WhisperX to transcribe audio, align word timings, and persist transcript segments plus artifacts. 【F:apps/workers/workers/tasks/transcription.py†L1-L216】【F:apps/workers/workers/tasks/alignment.py†L1-L215】 |
| **Clip Discovery & Styling** | OpenCLIP-powered discovery blends motion, audio, keywords, and duration targets using environment-configured weights, while pysubs2 styling applies brand-aware presets before registering subtitle artifacts. 【F:apps/workers/workers/tasks/clip_discovery.py†L1-L356】【F:apps/workers/workers/tasks/subtitle_render.py†L1-L274】 |
| **TTS & Export** | Coqui TTS synthesises dubbed audio, mixes narration with calibrated loudness, and registers stems, while FFmpeg export appends intro/outro slates, applies watermark overlays, and uploads the branded master render. 【F:apps/workers/workers/tasks/tts.py†L1-L244】【F:apps/workers/workers/tasks/export.py†L1-L260】 |
| **Retell Synthesis** | Narrative summaries and outlines are generated from transcripts and persisted with accompanying artifacts. 【F:apps/workers/workers/tasks/retell.py†L1-L205】 |
| **Billing & Midtrans** | Billing repositories persist subscriptions, usage, and payment attempts while the Midtrans service interacts with Snap/Core APIs using configurable credentials. 【F:apps/api/app/repositories/billing.py†L1-L419】【F:apps/api/app/services/midtrans.py†L1-L237】 |
| **Compliance & Observability** | DMCA, audit logging, and metrics endpoints persist structured records instead of logging placeholders. 【F:apps/api/app/repositories/dmca.py†L1-L159】【F:apps/api/app/repositories/observability.py†L1-L196】 |
| **Branding & Dashboard UX** | Brand kits persist in Postgres, API endpoints expose CRUD operations and presigned asset uploads, and the React dashboard lets editors manage brand libraries, split/merge clip segments on waveform timelines, and receive toast notifications for job events. 【F:apps/api/app/api/routes/branding.py†L1-L238】【F:apps/ui/src/components/BrandKitManager.tsx†L1-L336】【F:apps/ui/src/components/ClipEditor.tsx†L1-L412】 |
| **Telemetry & QA Review** | Prometheus/OpenTelemetry instrumentation is wired for API/workers, QA runs persist overlay/assignment metadata, and the dashboard lets reviewers assign owners, inspect overlays, and submit approvals inline. 【F:apps/api/app/telemetry/__init__.py†L1-L120】【F:apps/api/app/domain/qa.py†L1-L118】【F:apps/api/app/api/routes/observability.py†L1-L240】【F:apps/ui/src/components/QAQualitySummary.tsx†L1-L520】 |
| **CI & Smoke Tests** | GitHub Actions workflow builds API/workers/UI, runs QA regression checks, and executes an API smoke test that provisions a user/org/project via FastAPI. 【F:.github/workflows/ci.yml†L1-L74】【F:scripts/smoke_test.py†L1-L78】 |
| **Infrastructure blueprints** | Kubernetes manifests cover Postgres, Redis, MinIO, API, Celery workers, and an OTLP collector so the documented architecture can be deployed on-cluster. 【F:infra/k8s/postgres.yaml†L1-L41】【F:infra/k8s/api-deployment.yaml†L1-L62】 |

## Gaps Identified
Despite the breadth of endpoints, several critical execution paths remain incomplete:

1. **Media QA Expansion**
   The regression harness records findings with overlay metadata, assignments, reviewer notes, and golden-reference artifact IDs; it still needs automated diff/heatmap generation, richer multilingual fixtures, and collaborative annotation workflows to cover frame-level issues.

2. **Editorial Workspace Depth**
   Timeline scrubbing, waveform previews, and split/merge operations are in place, yet ripple edits, keyboard shortcuts, retell script editors, and brand-kit asset versioning still need to land to hit the full creative brief.

3. **Observability Automation**
   Prometheus/Otel exporters are wired, although alert routing, SLO dashboards, and an expanded webhook catalog (e.g., `clip.styled`, `export.completed`) still need to be codified for downstream automation.

4. **Production Hardening**
   Baseline Kubernetes manifests and CI are available; the next step is templating secrets management, GPU node pools, canary rollouts, and cost monitoring so the platform can scale safely in production.

## Detailed Action Plan
The recommended sequence below addresses the remaining gaps while respecting the documented system flow.

1. **Expand Media QA Coverage**
   - Add fixture scenarios for additional locales, long-form documentaries, and branded exports, persisting rendered comparisons that pair with the stored artifact IDs.
   - Layer in frame-diff heatmaps and annotation trails so creative directors can approve or request fixes without leaving the QA view.

2. **Deepen Editorial UX**
   - Layer in ripple timeline edits, keyboard shortcuts, waveform zoom, and undo/redo so editors can work at speed.
   - Add retell script editors, brand-kit asset versioning workflows, and quota warnings tied to billing usage snapshots.

3. **Observability & Automation**
   - Publish Prometheus rules + Grafana dashboards, wire alert routing, and expand webhook topics beyond job lifecycle events to cover clips, exports, and billing thresholds.
   - Stream queue depth/runtime metrics into the dashboard to highlight bottlenecks alongside QA coverage.

4. **Infrastructure & Delivery**
   - Extend the Kubernetes manifests with GPU node scheduling hints, secret management templates, and canary rollout strategies.
   - Integrate the CI smoke test with artefact publishing, database migrations, and cost monitoring hooks to complete the production readiness story.

## Monitoring & Documentation Updates
- Keep `docs/10-roadmap.md` synchronized with each completed milestone by moving items from the gap list into the progress list.
- Document new environment variables (e.g., model cache directories, external API keys) in `.env.example` as new workers are implemented.
- Update `docs/32-api-contract.md` with execution notes when endpoints transition from "queue only" to "fully automated" to avoid ambiguous status.

## Risks & Mitigations
- **Model Runtime Footprint:** Torch-based components will require GPU provisioning; capture requirements in infrastructure docs and provide CPU fallbacks for development.
- **Long-Running Tasks:** Ensure Celery queues use per-step timeouts and support resume/retry semantics already exposed by the API.
- **Cost Management:** Billing usage increments must reflect actual compute/storage costs once pipelines run—hook metrics into usage reporting immediately after each worker completes.

## Immediate Next Steps

The following workstreams are queued for the upcoming sprint to close the remaining gaps while keeping the product roadmap aligned with the documented flow:

1. **QA & Creative Approval Enhancements**
   - Extend the regression dataset with multilingual dubbing, branded subtitle variants, and long-form retell scenarios.
   - Generate frame-diff overlays and waveform snapshots for failing findings so reviewers can triage issues without downloading raw artifacts.
   - Layer automated reminders (email/Slack) and escalation paths on top of the new due-date/status workflow so overdue findings surface proactively.

2. **Editorial Workspace Depth**
   - Deliver ripple edits, keyboard shortcuts, undo/redo, and zoomable waveform timelines within the clip editor.
   - Add retell script editing, brand-kit asset version history, and quota warnings that surface when billing limits approach thresholds.

3. **Observability Automation**
   - Publish Prometheus alert rules and Grafana dashboards using the metrics emitted by the API/workers/QA harness.
   - Expand webhook topics (e.g., `clip.styled`, `export.completed`, `qa.run.failed`) and surface queue-depth heatmaps in the dashboard for proactive monitoring.

4. **Production Delivery Hardening**
   - Template Kubernetes secrets, add GPU node selectors/tolerations, and codify blue/green rollout manifests.
   - Integrate the smoke tests and QA harness into the CI artifact pipeline, including database migrations and rollback validation steps.

Each item above is tracked in the roadmap and will be checked off in documentation as it lands so stakeholders can verify progress against the planned application flow.

