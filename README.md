# Viral Clip AI Monorepo

Fitur **AI Viral Clip** untuk mengubah 1 video panjang menjadi banyak clip pendek yang berpotensi viral.
Monorepo ini berisi:

- `backend/` — FastAPI + SQLite + worker.
- `frontend/` — React + TypeScript + Tailwind + Framer Motion.
- `docs/` — dokumentasi lengkap per fase pengembangan.

Lihat `docs/` untuk penjelasan detail tiap fase.

## Menjalankan

- Backend API: `cd backend && uvicorn app.main:app --reload`
- Worker: `cd backend && python -m app.worker.main`
- Frontend: `cd frontend && npm install && npm run dev` (login/register di UI)
- Database migrate (wajib sebelum run): `cd backend && alembic upgrade head`
- Generate OpenAPI spec: `cd backend && python scripts/generate_openapi.py`

Prasyarat: ffmpeg/ffprobe terpasang di PATH.

Set environment variables (contoh `.env` di folder `backend`):

```
OPENAI_API_KEY=your_key_here
APP_ENV=dev
DATABASE_URL=sqlite:///./app.db
BACKEND_CORS_ORIGINS=["http://localhost:5173"]
MEDIA_ROOT=media
MEDIA_BASE_URL=http://localhost:8000/media
FFMPEG_BIN=ffmpeg
FFPROBE_BIN=ffprobe
OPENAI_WHISPER_MODEL=whisper-1
OPENAI_RESPONSES_MODEL=gpt-4o-mini
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_VOICE=alloy
CREDIT_COST_PER_MINUTE=1
```

## Ops (ringkas)

- **systemd service contoh**:
  - `/etc/systemd/system/viralclip-api.service` → ExecStart `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - `/etc/systemd/system/viralclip-worker.service` → ExecStart `python -m app.worker.main`
- **Nginx**:
  - Reverse proxy `/api` → `http://127.0.0.1:8000`
  - Serve `/media` langsung ke direktori media.
- **Backup**: salin `app.db` + direktori `media/` secara berkala.
- **Monitoring**: aktifkan logging stdout systemd + tail journal; tambahkan alerts dasar untuk kegagalan service.
