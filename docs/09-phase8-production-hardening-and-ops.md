# 09 – Phase 8: Production Hardening & Ops

## 1. Goal

Menjadikan sistem layak dipakai user awal (early customers):

- Logging & monitoring.
- Error handling konsisten.
- Backup & migration story.
- Rate limiting & credit system dasar.

## 2. Logging

- Gunakan `structlog` atau `logging` bawaan:
  - Log setiap job mulai/selesai.
  - Log panggilan AI (provider, model, tokens).
- Simpan ke file log + stdout.

## 3. Error Handling

- Global exception handler di FastAPI:
  - Kembalikan JSON dengan `error_code` & `message`.
- Worker:
  - Jika job gagal:
    - `processing_jobs.status = "failed"`.
    - set `error_message`.
- UI:
  - Tampilkan error toast jika API mengembalikan error.

## 4. Rate Limiting & Credits

- Tambah field `credits` di `users`.
- Aturan:
  - 1 menit video = X credits.
- Setiap kali memulai `clip_batch`, hitung durasi & kurangi credits.
- Jika credits tidak cukup → tolak request.

## 5. Security

- Pastikan:
  - CORS hanya untuk domain frontend.
  - Gunakan HTTPS di server.
  - Simpan `OPENAI_API_KEY` di environment, tidak di git.

## 6. Deployment Basic

- Gunakan Nginx sebagai reverse proxy:
  - `/api` diarahkan ke FastAPI (uvicorn).
  - `/` diarahkan ke static frontend build.
- Systemd service untuk:
  - `viralclip-api`
  - `viralclip-worker`

## 7. Backups & Migration

- SQLite:
  - Backup file `app.db` berkala.
- Rencana migrasi:
  - Gunakan SQLAlchemy + Alembic sehingga bisa pindah ke Postgres dengan mengganti `DB_URL`.

## 8. Testing Akhir

- Load test ringan (locust / vegeta) untuk endpoint utama.
- Integrasi test:
  - Flow penuh 1 video 5–10 menit:
    - Submit → Job → Clips ready → Export → Download.