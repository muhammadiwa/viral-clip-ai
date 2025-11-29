# 04 – Phase 3: Transcription & Segmentation

## 1. Goal

Mengubah worker dummy menjadi pipeline dasar:

1. Download / akses video.
2. Ekstrak audio.
3. Transkripsi audio.
4. Simpan transcript ke DB.
5. Segmentasi video menjadi scene segments (waktu start/end) sebagai kandidat clip.

Belum ada virality scoring; baru segmentation.

## 2. Data Model Tambahan

### 2.1. TranscriptSegment

Tabel: `transcript_segments`

- `id`
- `video_source_id`
- `start_time_sec: float`
- `end_time_sec: float`
- `text: str`
- `speaker: str | None`
- `language: str` (ISO code, misal `en`, `id`)

### 2.2. SceneSegment

Tabel: `scene_segments`

- `id`
- `video_source_id`
- `start_time_sec`
- `end_time_sec`
- `score_energy: float | None` (intensitas audio)
- `score_change: float | None` (perubahan dari scene sebelumnya)

## 3. Integrasi STT (Whisper / Audio API)

Gunakan:

- OpenAI Whisper (`audio/transcriptions`) atau model lokal.
- Simpan transcript per segment.

Langkah pipeline:

1. Ambil video file.
2. Jalankan ffmpeg:
   - Ekstrak audio ke `.wav` atau `.mp3`.
3. Kirim audio ke OpenAI Whisper (padding chunk kalau durasi besar).
4. Dari hasil:
   - Map ke segments: `start`, `end`, `text`.
5. Insert ke `transcript_segments`.

## 4. Scene Detection

Sederhana dulu:

- Gunakan energi audio dan silence detection dengan ffmpeg.
- Atau gunakan library `pyscenedetect`.
- Hasilkan list `(start, end)`.

Insert ke `scene_segments`.

## 5. Worker Flow (Update)

Pseudo:

1. Ambil job `transcription_and_clipping`.
2. Download / locate video.
3. Transcription:
   - Update `progress` (0–40).
4. Segmentation:
   - Hitung scenes & simpan (40–70).
5. Tandai `video_sources.status = "analyzed"`.
6. Job selesai (`completed`).

## 6. Endpoint Tambahan

### 6.1. GET /viral-clip/videos/{id}/transcript

Return list `transcript_segments` untuk debugging.

### 6.2. GET /viral-clip/videos/{id}/scenes

Return list `scene_segments`.

## 7. Testing Checklist

- ✅ Jalankan job pada video pendek (~5–10 menit).
- ✅ Transcript tersimpan dan bisa dibaca dari endpoint.
- ✅ Scene segmentation masuk.
- ✅ Error logging kalau STT gagal atau file rusak.