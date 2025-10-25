# Environment Setup Reference

This reference catalogs every environment file, explains the variables they expose, and outlines the commands you can use to validate local development and production deployments.

## TL;DR Workflow

| Goal | Commands |
| --- | --- |
| Bootstrap local development | `make dev-setup` → `make dev-up` |
| Tear down local development | `make dev-down` or `make dev-clean` |
| Prepare production secrets | `make prod-setup` then edit `.env.production` |
| Launch production stack (Docker) | `make prod-up` |
| Audit environment readiness | `make env-check` |

All commands rely on the refreshed Makefile and docker wrapper. The wrapper automatically selects the native `docker` CLI or falls back to Docker Desktop inside WSL.

## Tracked Templates

| File | Purpose | Notes |
| --- | --- | --- |
| `.env.development` | Safe defaults for local Docker Compose | Copy to `.env` for development (`make dev-setup` does this automatically). |
| `.env.production.sample` | Placeholder values for production secrets | Copy to `.env.production` and replace all `<placeholder>` entries using your secret manager. |
| `.env` | Local developer overrides | Ignored by git; generated from `.env.development`. |
| `.env.production` | Real production values | Ignored by git; generated from `make prod-setup`. |

> **Tip:** Compose interpolation happens before containers start. Ensure the desired env file exists in the same directory before running `docker compose`.

## Key Variables by Area

### Core API (`apps/api/app/core/config.py`)

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | JWT signing secret; rotate regularly in prod. |
| `CORS_ORIGINS` | JSON array of allowed origins (e.g. `["https://app.example.com"]`). |
| `DATABASE_URL` | `postgresql+asyncpg://…` DSN. |
| `REDIS_URL` | Broker/result backend for rate limiting and Celery. |
| `WORKER_SERVICE_TOKEN` | Shared secret for worker → API callbacks. |
| `ENABLE_PROMETHEUS_METRICS`, `PROMETHEUS_METRICS_PATH` | Toggle FastAPI metrics endpoint. |
| `OTEL_EXPORTER_OTLP_*` | OpenTelemetry collector configuration. |
| `PLAN_*`, `SUBSCRIPTION_*` | Billing/quota knobs. |

### Storage (MinIO / S3)

Set all of the following when using S3-compatible storage:

- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` (MinIO only)
- `S3_ENDPOINT_URL`
- `S3_BUCKET`
- `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- `S3_REGION`
- `S3_SECURE` (`true` for HTTPS endpoints)
- `STORAGE_UPLOAD_EXPIRY_SECONDS`

### Worker/Model Configuration (`apps/workers`)

- `API_BASE_URL` — internal address workers call to reach the API (`http://api:8000` in Compose).
- `WORKER_PROMETHEUS_PORT` / `WORKER_PROMETHEUS_HOST` — exports Celery metrics when set.
- Model weights & scoring knobs: `WHISPER_MODEL_NAME`, `CLIP_*`, `TTS_*`, etc.

### Frontend (Vite)

- `VITE_API_BASE_URL` — base URL baked into the React bundle. Provided through `.env` / `.env.production` so both dev and prod builds stay in sync.

### Billing (Midtrans)

- `MIDTRANS_SERVER_KEY`, `MIDTRANS_CLIENT_KEY`, `MIDTRANS_IS_PRODUCTION`, `MIDTRANS_APP_NAME`

## Docker Compose Layout

### Development (`docker-compose.dev.yml`)

- Includes Postgres, Redis, MinIO, API, UI (hot reload), Celery workers, observability helpers (Flower, Adminer, Redis Commander), and Nginx.
- Mounts source directories for live reload in API and UI containers.
- Host ports are configurable via `.env` (e.g. `NGINX_HTTP_PORT=8080`).
- Run with `make dev-up` (equivalent to `docker compose --env-file .env -f docker-compose.dev.yml up -d`).

### Production (`docker-compose.prod.yml`)

- Builds release images (API, UI, workers) without dev-only tools.
- Exposes Postgres/MinIO ports for operational access; adjust or remove in production firewalls.
- Requires `.env.production` populated with real secrets. Launch via `make prod-up` or:
  ```bash
  docker compose --env-file .env.production -f docker-compose.prod.yml up -d
  ```

### Kubernetes

The manifests under `infra/k8s/` expect a `viral-clip-secrets` secret containing the same keys defined above (`DATABASE_URL`, `S3_*`, `SECRET_KEY`, `WORKER_SERVICE_TOKEN`, `MIDTRANS_*`, etc.). Keep MinIO/S3 credentials, JWT secrets, and Midtrans keys in your preferred vault and sync them into the cluster.

## Validation Checklist

1. Run `make env-check` to confirm templates exist and no obvious placeholders remain.
2. Run `./docker-wrapper.sh compose --env-file .env -f docker-compose.dev.yml config` to validate the dev stack renders correctly.
3. Run `./docker-wrapper.sh compose --env-file .env.production -f docker-compose.prod.yml config` before production deploys.
4. For Kubernetes, ensure `kubectl get secret viral-clip-secrets -n viral-clip-ai` lists the required keys.

## Common Pitfalls

- **Missing `.env`**: Compose warns about empty variables. Fix by copying `.env.development` -> `.env` or exporting values in your shell.
- **Incorrect `CORS_ORIGINS` format**: Provide a JSON array. Pydantic rejects plain comma-separated strings for `List[AnyHttpUrl]`.
- **Vite API URL mismatch**: Update both `.env` (for dev) and `.env.production` (for build) so the dashboard points to the correct backend.
- **Placeholder secrets in production**: `make env-check` highlights `<placeholder>` strings. Replace them before shipping.

## Related Commands

- `make dev-status` / `make prod-status` – list running containers.
- `make dev-logs` / `make prod-logs` – tail logs across services.
- `make migrate` – run Alembic migrations from the host environment.

Use this document alongside `DEPLOYMENT-GUIDE.md` for infrastructure-specific steps (Kubernetes, scaling, backups, etc.).
