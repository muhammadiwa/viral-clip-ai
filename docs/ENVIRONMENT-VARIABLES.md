# Environment Variables Documentation

## Struktur dan Organisasi

Dokumen ini menjelaskan semua environment variables yang digunakan dalam Viral Clip AI, bagaimana mereka diorganisir, dan mencegah duplikasi.

---

## 1. Database Configuration

### PostgreSQL Credentials
Digunakan oleh: PostgreSQL container, FastAPI, Alembic migrations

```bash
# Credentials utama (shared by all services)
POSTGRES_USER=viralclip
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=viralclip

# Connection details untuk API container
DB_HOST=postgres  # Docker Compose service name
DB_PORT=5432

# Connection string untuk FastAPI (asyncpg driver)
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${DB_HOST}:${DB_PORT}/${POSTGRES_DB}
```

**Catatan:**
- `POSTGRES_*` adalah source of truth untuk credentials
- `DB_HOST` dan `DB_PORT` digunakan oleh Alembic untuk membentuk connection string
- `DATABASE_URL` digunakan langsung oleh FastAPI/SQLAlchemy
- **TIDAK ADA** duplikasi `DB_USER`, `DB_PASSWORD`, `DB_NAME` lagi!

---

## 2. Redis Configuration

### Single Redis URL
Digunakan oleh: FastAPI (rate limiting), Celery (broker & backend)

```bash
# Single source of truth untuk Redis
REDIS_URL=redis://redis:6379/0
```

**Catatan:**
- `CELERY_BROKER_URL` dan `CELERY_RESULT_BACKEND` DIHAPUS dari .env
- FastAPI `config.py` sudah memiliki fallback logic:
  ```python
  celery_broker_url: str | None  # Falls back to redis_url if None
  celery_result_backend: str | None  # Falls back to broker if None
  ```
- Tidak ada duplikasi environment variable!

---

## 3. Object Storage (MinIO/S3)

### Storage Credentials
Digunakan oleh: MinIO container, API, Workers

```bash
# MinIO container credentials (source of truth)
MINIO_ROOT_USER=viralclipadmin
MINIO_ROOT_PASSWORD=<secure-password>

# S3 client configuration (uses same credentials as MinIO)
S3_ENDPOINT_URL=http://51.38.236.105:9002
S3_BUCKET=viral-clip-ai
S3_ACCESS_KEY=viralclipadmin  # Same as MINIO_ROOT_USER
S3_SECRET_KEY=<secure-password>  # Same as MINIO_ROOT_PASSWORD
S3_REGION=us-east-1
S3_SECURE=false
STORAGE_UPLOAD_EXPIRY_SECONDS=900
```

**Catatan:**
- `MINIO_ROOT_USER` = `S3_ACCESS_KEY` (same value)
- `MINIO_ROOT_PASSWORD` = `S3_SECRET_KEY` (same value)
- Ini adalah duplikasi yang **DIPERLUKAN** karena:
  - MinIO container menggunakan `MINIO_ROOT_*`
  - boto3 client (di API/Workers) menggunakan `S3_ACCESS_KEY`/`S3_SECRET_KEY`
- MinIO di-expose di port **9002** (API) dan **9003** (console) untuk menghindari konflik

---

## 4. API & Worker Communication

```bash
# API base URL untuk workers
API_BASE_URL=http://api:8000

# Shared secret untuk autentikasi workers
WORKER_SERVICE_TOKEN=<secure-token>

# Prometheus metrics untuk workers
WORKER_PROMETHEUS_PORT=9200
WORKER_PROMETHEUS_HOST=0.0.0.0
```

---

## 5. Frontend Configuration

```bash
# API base URL untuk React UI (public-facing)
VITE_API_BASE_URL=http://51.38.236.105:8000

# QA reporting configuration
QA_REPORT_API_BASE_URL=http://api:8000
QA_REPORT_TOKEN=
QA_REPORT_ORG_ID=
```

---

## 6. Core API Settings

```bash
PROJECT_NAME=Viral Clip AI API
API_V1_PREFIX=/v1
SECRET_KEY=<secure-key>  # JWT signing key
ACCESS_TOKEN_EXPIRE_MINUTES=60
RATE_LIMIT_REQUESTS_PER_MINUTE=120
RATE_LIMIT_WINDOW_SECONDS=60
SUBSCRIPTION_TRIAL_DAYS=14
SUBSCRIPTION_CYCLE_DAYS=30
CORS_ORIGINS=["http://51.38.236.105","http://51.38.236.105:80","http://51.38.236.105:3000"]
DEFAULT_ORG_ID=
```

---

## 7. AI/ML Model Configuration

```bash
# Whisper (ASR)
WHISPER_MODEL_NAME=base
WHISPER_COMPUTE_TYPE=float16

# WhisperX (Alignment)
ALIGNMENT_MODEL_NAME=WAV2VEC2_ASR_BASE_960H
ALIGNMENT_DEVICE=  # Auto-detect: cuda/cpu

# CLIP (Vision)
CLIP_MODEL_NAME=ViT-B-32
CLIP_MODEL_PRETRAINED=openai
CLIP_SAMPLE_INTERVAL_SECONDS=2
CLIP_MOTION_WEIGHT=0.5
CLIP_AUDIO_WEIGHT=0.3
CLIP_KEYWORD_WEIGHT=0.2
CLIP_DURATION_WEIGHT=0.15
CLIP_CONFIDENCE_BIAS=0.25
CLIP_CONFIDENCE_THRESHOLD=0.55
CLIP_MIN_DURATION_SECONDS=12
CLIP_MAX_DURATION_SECONDS=45
CLIP_TARGET_DURATION_SECONDS=22

# TTS (XTTS v2)
TTS_MODEL_NAME=tts_models/multilingual-multi-dataset/xtts_v2
TTS_SPEAKER_WAV=
TTS_MUSIC_GAIN_DB=-9.0
TTS_VOICE_GAIN_DB=-1.5
TTS_LOUDNESS_TARGET_I=-16.0
TTS_LOUDNESS_TRUE_PEAK=-1.5
TTS_LOUDNESS_RANGE=11.0

# Retell (Summary)
RETELL_SUMMARY_SENTENCES=8
```

---

## 8. Video Export Configuration

```bash
# FFmpeg settings
EXPORT_VIDEO_PRESET=veryfast

# Branding assets
EXPORT_BRAND_INTRO_OBJECT_KEY=
EXPORT_BRAND_OUTRO_OBJECT_KEY=
EXPORT_WATERMARK_OBJECT_KEY=
EXPORT_WATERMARK_POSITION=bottom-right
EXPORT_WATERMARK_SCALE=0.18
```

---

## 9. Subtitle Configuration

```bash
SUBTITLE_DEFAULT_PRESET=brand-kit
SUBTITLE_BRAND_PRESET_NAME=brand-kit
SUBTITLE_BRAND_FONT_FAMILY=
SUBTITLE_BRAND_TEXT_COLOR=
SUBTITLE_BRAND_BACKGROUND_COLOR=
SUBTITLE_BRAND_STROKE_COLOR=
SUBTITLE_BRAND_HIGHLIGHT_COLOR=
SUBTITLE_BRAND_UPPERCASE=false
```

---

## 10. Billing & Pricing (Midtrans)

```bash
# Plan pricing (IDR)
PLAN_PRICE_FREE_IDR=0
PLAN_PRICE_PRO_IDR=299000
PLAN_PRICE_BUSINESS_IDR=899000

# Quota limits
PLAN_MINUTES_QUOTA_FREE=600
PLAN_MINUTES_QUOTA_PRO=3000
PLAN_MINUTES_QUOTA_BUSINESS=10000
PLAN_CLIP_QUOTA_FREE=50
PLAN_CLIP_QUOTA_PRO=250
PLAN_CLIP_QUOTA_BUSINESS=1000
PLAN_RETELL_QUOTA_FREE=5
PLAN_RETELL_QUOTA_PRO=40
PLAN_RETELL_QUOTA_BUSINESS=120
PLAN_STORAGE_QUOTA_GB_FREE=50
PLAN_STORAGE_QUOTA_GB_PRO=250
PLAN_STORAGE_QUOTA_GB_BUSINESS=1024

# Midtrans payment gateway
MIDTRANS_SERVER_KEY=SB-Mid-server-dummy
MIDTRANS_CLIENT_KEY=SB-Mid-client-dummy
MIDTRANS_IS_PRODUCTION=false
MIDTRANS_APP_NAME=Viral Clip AI
```

---

## 11. Observability

```bash
# Prometheus metrics
ENABLE_PROMETHEUS_METRICS=true
PROMETHEUS_METRICS_PATH=/metrics/prometheus

# OpenTelemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
OTEL_SERVICE_NAME=viral-clip-api
```

---

## 12. Infrastructure

```bash
# Nginx reverse proxy
NGINX_HTTP_PORT=80
```

---

## Prinsip Organisasi

### ✅ DO's (Yang Benar)
1. **Single Source of Truth**: Setiap nilai hanya didefinisikan SEKALI
2. **Meaningful Grouping**: Group variables berdasarkan service/fungsi
3. **Clear Comments**: Dokumentasikan penggunaan dan dependencies
4. **Consistent Naming**: Gunakan prefix yang konsisten (e.g., `POSTGRES_*`, `S3_*`)

### ❌ DON'Ts (Yang Salah)
1. **Duplikasi Tidak Perlu**: Jangan buat `DB_USER` DAN `POSTGRES_USER` dengan nilai sama
2. **Redundant References**: Hindari `CELERY_BROKER_URL=${REDIS_URL}` jika sudah ada fallback logic
3. **Inconsistent Values**: Pastikan nilai yang sama tidak didefinisikan berbeda di tempat lain

### ⚠️ Allowed Duplication
Duplikasi HANYA diperbolehkan jika:
- **Different Naming Convention Required**: e.g., MinIO butuh `MINIO_ROOT_USER` tapi boto3 butuh `S3_ACCESS_KEY`
- **External API Requirement**: e.g., Midtrans butuh format tertentu
- **Clear Documentation**: Harus didokumentasikan dengan jelas bahwa nilai harus sama

---

## Migration dari Struktur Lama

### Sebelum (Redundant)
```bash
# ❌ WRONG: Duplikasi database credentials
POSTGRES_USER=viralclip
DB_USER=viralclip
POSTGRES_PASSWORD=xxx
DB_PASSWORD=xxx
POSTGRES_DB=viralclip
DB_NAME=viralclip
DB_HOST=postgres
DB_PORT=5432
DATABASE_URL=postgresql+asyncpg://viralclip:xxx@postgres:5432/viralclip

# ❌ WRONG: Duplikasi Redis URL
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

### Sesudah (Clean)
```bash
# ✅ CORRECT: Single source of truth
POSTGRES_USER=viralclip
POSTGRES_PASSWORD=xxx
POSTGRES_DB=viralclip
DB_HOST=postgres
DB_PORT=5432
DATABASE_URL=postgresql+asyncpg://viralclip:xxx@postgres:5432/viralclip

# ✅ CORRECT: Single Redis URL (fallback handled in code)
REDIS_URL=redis://redis:6379/0
```

---

## Verification Checklist

Sebelum deploy, pastikan:

- [ ] Tidak ada duplikasi variable dengan nilai sama
- [ ] Semua secrets/passwords sudah diganti dari default
- [ ] `CORS_ORIGINS` sudah sesuai dengan deployment URL
- [ ] `S3_ACCESS_KEY` = `MINIO_ROOT_USER`
- [ ] `S3_SECRET_KEY` = `MINIO_ROOT_PASSWORD`
- [ ] `DATABASE_URL` sesuai dengan `POSTGRES_*` credentials
- [ ] Port mapping tidak konflik dengan service lain di VPS
- [ ] Comment dan dokumentasi sudah jelas

---

**Last Updated**: 2025-10-25  
**Status**: ✅ Production-Ready
