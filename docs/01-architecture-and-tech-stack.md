# 01 – Architecture & Tech Stack

## 1. High-Level Architecture

Komponen:

1. **Web Frontend**
   - React + TypeScript + Vite.
   - Tailwind CSS + Framer Motion.
   - Berkomunikasi ke FastAPI via JSON REST.

2. **Backend API (FastAPI)**
   - Menyediakan:
     - Auth & user management.
     - Endpoint untuk upload video / submit YouTube URL.
     - Endpoint membaca status job dan list clips.
     - Endpoint untuk generate/export clip.
   - Menulis ke SQLite via SQLAlchemy.

3. **Video Processing Worker**
   - Python process terpisah (bisa `fastapi` background task dulu, lalu dinaikkan jadi worker).
   - Mengambil job dari tabel `processing_jobs`.
   - Melakukan:
     - Download / ekstrak audio.
     - Panggil STT (Whisper API OpenAI).
     - Segmentasi waktu.
     - Panggil OpenAI Responses API untuk scoring & pembuatan title, caption, dsb.
     - Generate subtitle + simpan ke DB/file.
     - Trigger export (ffmpeg) bila diminta.

4. **Storage**
   - Local disk dulu: `media/videos`, `media/clips`, `media/subtitles`.
   - Path disimpan di SQLite.
   - Bisa diganti ke S3 nanti.

## 2. Tech Stack Detail

### 2.1. Backend

- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy + Alembic
- SQLite
- HTTPX (panggil API AI)
- python-multipart (upload file)
- Pydantic v2
- ffmpeg (CLI di sistem + wrapper Python)
- openai Python SDK untuk Responses + Audio.

Respon text/analisis akan menggunakan **Responses API** OpenAI karena itu interface terbaru yang direkomendasikan untuk text generation. :contentReference[oaicite:1]{index=1}  

### 2.2. Frontend

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- React Query atau SWR (data fetching & cache)

### 2.3. Deployment & Ops (minimal)

- 1 VPS Linux (Ubuntu)
- Reverse proxy: Nginx
- Systemd service:
  - `viralclip-api.service`
  - `viralclip-worker.service`
  - `viralclip-frontend.service` (Vite build static + Nginx)

## 3. Core Data Model (Ringkas)

- `users`
- `video_sources`
- `clip_batches` (konfigurasi AI clipping per video)
- `clips`
- `subtitle_segments`
- `subtitle_styles`
- `brand_kits`
- `exports`
- `processing_jobs`
- `ai_usage_logs`

Detail perubahan per fase dijelaskan di dokumen fase masing-masing.

## 4. Security & Config

- Env file:
  - `OPENAI_API_KEY`
  - `APP_ENV` (dev/prod)
  - `FFMPEG_BIN` (opsional)
  - `DB_URL` (default `sqlite:///./app.db`)
- Rate limiting (minimal):
  - Limit per user/hari untuk job `Get Clips`.
- API keys & secrets jangan hardcode.