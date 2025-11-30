# 03 – Phase 2: Video Ingest & Job Management

## 1. Goal

Menambahkan kemampuan untuk:

- Menerima YouTube URL dan file upload.
- Menyimpan metadata video ke SQLite.
- Membuat `processing_jobs` untuk pipeline AI.
- Menampilkan riwayat video per user.

Belum ada AI; hanya infrastruktur job.

## 2. Data Model

### 2.1. VideoSource

Tabel: `video_sources`

- `id: int`
- `user_id: int`
- `source_type: str` (`youtube`, `upload`)
- `source_url: str | None`
- `file_path: str | None` (path lokal)
- `title: str | None`
- `duration_seconds: int | None`
- `status: str` (`pending`, `processing`, `ready`, `failed`)
- `error_message: str | None`
- `created_at: datetime`
- `updated_at: datetime`

### 2.2. ProcessingJob

Tabel: `processing_jobs`

- `id`
- `video_source_id`
- `job_type` (misal `transcription_and_clipping`)
- `status` (`queued`, `running`, `completed`, `failed`)
- `progress: float` (0–100)
- `payload: JSON` (parameter; misalnya video_type, aspect_ratio)
- `result_summary: JSON | None`
- `created_at`
- `updated_at`

## 3. Endpoint Baru

### 3.1. POST /viral-clip/video/youtube

Body:

```json
{
  "youtube_url": "https://youtu.be/...",
  "video_type": "podcast",
  "aspect_ratio": "9:16",
  "clip_length_preset": "auto_0_60",
  "subtitle": true
}

Output:

    video_source object

    processing_job object (status queued)

3.2. POST /viral-clip/video/upload

    Multipart form:

        file: video file

        JSON fields untuk konfigurasi awal.

Simpan file ke media/videos/{user_id}/{uuid}.mp4.
3.3. GET /viral-clip/videos

    Auth required.

    Return list video_sources milik user, di-sort terbaru.

3.4. GET /viral-clip/jobs/{job_id}

Return status/progress job.
4. Worker Entry Point

Buat modul worker/main.py yang:

    Periodik (setiap X detik) mengecek processing_jobs berstatus queued.

    Mengubah status menjadi running.

    Menjalankan pipeline dummy:

        (Phase 2) cukup simulate: tidur 2 detik, update progress 100, ubah video_sources.status = "ready".

Pada phase Berikutnya pipeline ini diisi proses STT & segmentation.
5. Frontend Dampak

    Di halaman AI Viral Clip:

        Bagian atas: form youtube_url + upload button memanggil endpoint di atas.

        Bagian bawah: list video_sources (thumbnail dummy dulu).

        Status: pending/processing/ready ditampilkan.

6. Testing Checklist

    ✅ Bisa submit video YT & upload file.

    ✅ Entitas video_sources & processing_jobs tercipta benar.

    ✅ Riwayat video muncul sesuai user.

    ✅ Job dummy mengubah status menjadi ready tanpa error.