# 00 – Product Overview

## 1. Visi Produk

**Viral Clip AI** adalah salah satu fitur utama di dalam platform “AI Studio”.
Tanpa konsep *project* di UI — user cukup:

1. Klik menu **AI Viral Clip** dari sidebar.
2. Paste link YouTube atau upload video panjang.
3. AI memproses dan menampilkan:
   - Banyak clip pendek yang berpotensi viral.
   - Skor virality per clip (0–10) + breakdown (Hook, Flow, Value, Trend).
   - Subtitle otomatis dengan berbagai style.
4. User bisa:
   - Download clip / SRT.
   - Apply subtitle style / brand kit.
   - Generate dub/voice-over & audio.
   - Export siap upload ke Short/ Reels / TikTok.

## 2. Target User & Use Case

### 2.1. Target User
- YouTuber, TikToker, Instagram Reels creator.
- Podcast & webinar owner.
- Social media agency / brand.

### 2.2. Use Case Utama
- Mengubah 1 video podcast 1 jam menjadi 20–30 viral clips vertikal 30–60 detik.
- Membuat versi multi-bahasa (subtitle + dub).
- Menstandarisasi tampilan (subtitle style, watermark, logo, warna brand).

## 3. Fitur Utama

1. **Video Ingest**
   - Input: YouTube URL, file upload.
   - Simpan metadata & durasi.
2. **AI Clipping**
   - STT (transkripsi).
   - Segmentasi scene + candidate clips.
   - Skor virality & label (Hook/Story/CTA).
3. **Subtitle Engine**
   - Subtitle otomatis dari transcript.
   - Multi bahasa, auto-translate.
   - Preset style (MrBeast, Minimal, Cinematic, dll).
4. **Brand & Style**
   - Brand kit per user (logo, warna, default subtitle style).
   - Template layout untuk overlay & watermark.
5. **Audio & Dub**
   - Background music & sound effects.
   - AI dubbing multi-bahasa (TTS).
   - Auto-ducking.
6. **Export & Batch Processing**
   - Batch export semua clips → MP4.
   - Pilihan resolusi, FPS, aspect ratio.
7. **Analytics Ringan**
   - Clip view count (jika user input atau sync manual).
   - Jam penggunaan & estimasi jam yang dihemat.

## 4. Non-Functional Requirements

- FastAPI + SQLite (bisa di-migrate ke Postgres).
- Terstruktur per fase development dengan dokumentasi ini.
- Logging dan error handling jelas.
- Konfigurasi AI provider via environment variables.
- Bisa jalan minimal di 1 VPS (1–2 worker untuk video processing).

## 5. Roadmap Fase

- Phase 1 – Backend foundation & auth.
- Phase 2 – Video ingest & job management.
- Phase 3 – Transcription & segmentation pipeline.
- Phase 4 – Virality scoring & clip generation (OpenAI LLM).
- Phase 5 – Subtitles, styles, brand kit.
- Phase 6 – Audio, dubbing & export pipeline.
- Phase 7 – Frontend Viral Clip UI & integration.
- Phase 8 – Production hardening, monitoring & ops.