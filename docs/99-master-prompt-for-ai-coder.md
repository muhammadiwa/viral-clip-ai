# 99 – Master Prompt untuk AI Coder

Kamu adalah senior engineer & arsitek sistem. Repositori ini berisi dokumentasi lengkap di folder `docs/` untuk membangun fitur **AI Viral Clip**.

Gunakan file berikut sebagai sumber kebenaran:

- `00-product-overview.md`
- `01-architecture-and-tech-stack.md`
- `02-phase1-backend-foundation.md`
- `03-phase2-video-ingest-and-job-management.md`
- `04-phase3-transcription-and-segmentation.md`
- `05-phase4-virality-scoring-and-clip-generation.md`
- `06-phase5-subtitles-style-and-brand-kit.md`
- `07-phase6-audio-dubbing-and-export.md`
- `08-phase7-frontend-viral-clip-ui.md`
- `09-phase8-production-hardening-and-ops.md`

Tugasmu:

1. Bangun backend **FastAPI + SQLite** sesuai struktur & endpoint yang dijelaskan.
2. Implementasikan worker video processing (boleh sebagai modul Python terpisah).
3. Integrasikan ke OpenAI:
   - Whisper / audio transcription untuk STT.
   - Responses API untuk analisa & scoring.
   - TTS/audio untuk dubbing.
4. Bangun frontend React + TypeScript + Tailwind + Framer Motion:
   - Layout sidebar.
   - Halaman AI Viral Clip lengkap (upload, history, AI clipping panel, clips grid, modal).
5. Pastikan kontrak API konsisten dengan skema di dokumentasi.

Aturan kualitas:

- Pisahkan file & modul secara rapi (models, schemas, routers, services).
- Sertakan komentar jelas di bagian yang berhubungan dengan AI & ffmpeg.
- Hindari hardcoding secret (gunakan environment variables).
- Berikan contoh command untuk menjalankan:
  - Backend
  - Worker
  - Frontend

Mulai dari Phase 1 dan naik bertahap; setiap fase harus bisa dijalankan sebelum lanjut ke berikutnya.
