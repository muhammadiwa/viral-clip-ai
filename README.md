
# Viral Clip AI — Monorepo Template (OSS-first)

This is a **production-ready template** to build the Viral Clip AI Generator:
- **apps/ui**: React + TypeScript + Vite + Tailwind + Framer Motion + r3f
- **apps/api**: FastAPI + Postgres + Redis + MinIO (S3) + JWT
- **apps/workers**: Celery queues (ingest/transcode/asr/nlp/subtitle/tts/render/retell/export/billing)
- **infra/docker**: `docker compose` with Postgres, Redis, MinIO, API, Workers, Nginx
- **docs**: split markdown docs

## Quickstart
```bash
cp .env.example .env
docker compose -f infra/docker/compose.yml up -d --build

# Open: http://localhost:8080  (UI via Nginx)
# API:  http://localhost:8080/api/healthz
# MinIO console: http://localhost:9001  (user/pass from .env)
```

> For local dev (without Docker), see docs and each app's README.

## Media QA Regression Checks & Creative Reviews

The worker heuristics now ship with a dataset-driven QA harness **and** a creative review workflow surfaced in the dashboard. The baseline fixture now spans multilingual clips, genre-aware subtitle presets, calibrated audio mixes, and frame-diff expectations so regression runs report coverage by locale/genre and flag timing drift. Run the regression suite locally before promoting changes to ensure clip scoring, subtitle presets, TTS mixing, and branded exports remain within calibrated ranges:

```bash
python -m apps.workers.workers.qa.runner
```

Provide a custom dataset with `--dataset path/to/file.json` when validating new scenarios. The default fixture lives at `apps/workers/workers/qa/datasets/baseline.json` and can be extended with additional clip, subtitle, mix, or export cases.

To capture regression history and power the dashboard quality widgets, export results with:

```bash
python -m apps.workers.workers.qa.runner \
  --report-json qa-report.json \
  --report-api-base ${QA_REPORT_API_BASE_URL} \
  --report-token ${QA_REPORT_TOKEN} \
  --report-org-id ${QA_REPORT_ORG_ID} \
  --artifact-map qa-artifacts.json
```

This records observability metrics (`qa.*`) and stores the structured run summary for creative review. Supply `--artifact-map` with a JSON object such as `{ "clip": { "balanced-highlight": ["<artifact-id>"] } }` (see `apps/workers/workers/qa/datasets/artifact-map.sample.json`) to link failing cases directly to generated artifact IDs; the dashboard will surface those IDs alongside reference URLs for faster creative audits. Inside the UI you can select any run, inspect locale/genre coverage, triage findings with overlay previews, assign owners (including “assign to me”), set due dates, move findings across the new in-progress/blocked/ready-for-review states, and submit approval/changes-required decisions that sync back to the API while triggering webhook notifications whenever assignments or schedules change.

## Brand Kits & Editorial Dashboard

- Create reusable brand kits (palette, typography, subtitle overrides, watermark/intro/outro objects) and assign them per-project.
- Upload watermark/logo/font/intro/outro assets through presigned MinIO flows; the dashboard tracks every asset with delete/preview controls so teams keep brand libraries tidy.
- Editors can adjust clip timing with waveform timelines, split/merge segments, snap to transcript bounds, scrub previews, and receive toast notifications when jobs succeed or fail in real time.
- Billing and quota summaries remain visible alongside project/job status for fast production decisions.

## Continuous Integration & Smoke Testing

- GitHub Actions workflow (`.github/workflows/ci.yml`) installs dependencies, builds the React dashboard, compiles API/worker modules, runs the QA baseline suite, and executes an API smoke test against a Postgres service.
- The smoke test (`scripts/smoke_test.py`) provisions a throwaway user/org, obtains a JWT, and creates a project through the FastAPI surface to validate end-to-end wiring.
- Keep CI green before shipping large media model updates to ensure telemetry, QA, and brand-kit tooling stay healthy.
