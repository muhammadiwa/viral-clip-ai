# 05 – Phase 4: Virality Scoring & Clip Generation

## 1. Goal

Dari transcript + scene, kita membuat:

- Candidate **clips** yang sudah memiliki:
  - start/end.
  - judul.
  - deskripsi singkat.
  - `viral_score` (0–10).
  - breakdown (Hook, Flow, Value, Trend).
- Tersimpan di tabel `clips`.

## 2. Data Model

### 2.1. ClipBatch

Tabel: `clip_batches`

- `id`
- `video_source_id`
- `name` (misal "default" / "first-run")
- `config_json`:
  - video_type
  - aspect_ratio
  - clip_length_preset
  - subtitle_enabled
  - processing_timeframe (start/end)
- `status` (draft/ready/final)
- `created_at`, `updated_at`

### 2.2. Clip

Tabel: `clips`

- `id`
- `clip_batch_id`
- `start_time_sec`
- `end_time_sec`
- `duration_sec`
- `title`
- `description`
- `viral_score: float`
- `grade_hook: str`
- `grade_flow: str`
- `grade_value: str`
- `grade_trend: str`
- `language: str`
- `status: str` (`candidate`, `edited`, `exported`)
- `thumbnail_path: str | None`

### 2.3. ClipLLMContext (opsional)

Tabel: `clip_llm_contexts` (untuk caching prompt/response mentah bila perlu debugging).

## 3. Prompting Design (OpenAI Responses API)

Gunakan model GPT terbaru via **Responses API** untuk:

- Menentukan kombinasi scene yang cocok jadi satu clip.
- Menilai `viral_score` dan breakdown.
- Membuat `title` dan `description` singkat.

Input ke LLM:

- Ringkasan video.
- Transkrip beberapa menit.
- Informasi `video_type` (podcast / gaming).
- Target durasi (misal 30–60 detik).

Output (JSON terstruktur):

```json
{
  "clips": [
    {
      "start_sec": 120.5,
      "end_sec": 153.2,
      "title": "Why Most People Fail at X",
      "description": "Short explanation about ...",
      "viral_score": 9.2,
      "grades": {
        "hook": "A",
        "flow": "A-",
        "value": "A",
        "trend": "B+"
      }
    }
  ]
}

Gunakan structured output / JSON mode di Responses API.
OpenAI Platform+1
4. Pipeline Langkah

    Worker baca clip_batches baru (dibuat saat user klik Get Clips dengan konfigurasi).

    Terapkan processing_timeframe ke daftar scene_segments.

    Gabungkan scene menjadi candidate windows dengan durasi mendekati clip_length_preset.

    Potong transcript sesuai window.

    Kirim ke OpenAI:

        1 call global untuk menyusun list clips, atau

        per window untuk scoring.

    Parse response, simpan sebagai clips.

    Generate thumbnail per clip via ffmpeg (ambil frame tengah).

    Tandai clip_batches.status = "ready".

5. Endpoint
5.1. POST /viral-clip/videos/{video_id}/clip-batches

Body:

    video_type

    aspect_ratio

    clip_length_preset

    subtitle_enabled

    processing_timeframe_start

    processing_timeframe_end

    include_specific_moments (string)

Response:

    clip_batch baru + job id.

5.2. GET /viral-clip/videos/{video_id}/clip-batches

Return list batch.
5.3. GET /viral-clip/clip-batches/{batch_id}/clips

Return list clips (untuk grid di UI).
5.4. GET /viral-clip/clips/{clip_id}

Return detail lengkap (untuk modal Segment Detail).
6. Testing Checklist

    ✅ Untuk 1 video, pipeline menghasilkan beberapa clips (≥5).

    ✅ Score & grades masuk akal (range 0–10).

    ✅ Thumbnail clip ada.

    ✅ Jika LLM gagal / error, job menulis error_message dan tidak crash worker.
