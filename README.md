
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
