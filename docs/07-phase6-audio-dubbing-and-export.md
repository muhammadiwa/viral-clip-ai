# 07 – Phase 6: Audio Dubbing & Export

## 1. Goal

- Tambahkan AI dubbing (TTS).
- Tambahkan background music & auto-ducking.
- Implementasi export pipeline (ffmpeg) yang menghasilkan MP4 siap pakai.

## 2. Data Model

### 2.1. AudioConfig (per clip)

Tabel: `audio_configs`

- `id`
- `clip_id`
- `bgm_track_id | NULL`
- `bgm_volume: float`
- `original_volume: float`
- `ai_voice_provider: str | NULL`
- `ai_voice_id: str | NULL`
- `language: str`
- `mode: str` (`replace`, `overlay`)

### 2.2. ExportJob

Tabel: `exports`

- `id`
- `clip_id`
- `resolution: str` (`720p`, `1080p`)
- `fps: int`
- `aspect_ratio: str`
- `status: str` (`queued`, `running`, `completed`, `failed`)
- `output_path: str | NULL`
- `created_at`
- `updated_at`

## 3. Dubbing Pipeline

1. Ambil `subtitle_segments` sebuah clip.
2. Gabungkan jadi script penuh.
3. Panggil TTS provider (misalnya OpenAI audio/speech, atau provider lain).
4. Dapat audio file dub (per clip).
5. Simpan ke `media/audio/dubs/...` dan catat di `audio_configs`.

## 4. Export Pipeline (Worker)

Untuk setiap `ExportJob`:

1. Ambil video source & time range clip.
2. Potong video menggunakan ffmpeg:
   - Apply crop/scale sesuai `aspect_ratio` & `resolution`.
3. Render subtitle:
   - Generate `.ass`/`.srt` style file berdasarkan `SubtitleStyle` & `BrandKit`.
4. Mix audio:
   - Original audio.
   - BGM (kalau ada).
   - Dub AI (kalau mode `replace` → ganti, kalau `overlay` → mix).
   - Gunakan filter `afade`, `sidechaincompress` untuk auto-ducking.
5. Hasilkan file MP4:
   - Simpan ke `media/clips/{clip_id}/{export_id}.mp4`.
6. Update `exports.status = "completed"` dan `output_path`.

## 5. Endpoint

### 5.1. POST /viral-clip/clips/{id}/exports

Body:

```json
{
  "resolution": "1080p",
  "fps": 30,
  "aspect_ratio": "9:16",
  "use_brand_kit": true,
  "use_ai_dub": true
}

Response:

    export object + job id.

5.2. GET /exports/{id}

Return status + download URL.
5.3. GET /viral-clip/clips/{id}/exports

List export per clip.
6. Testing Checklist

    ✅ Export satu clip berhasil (video + subtitle terbakar ke video).

    ✅ BGM terdengar dan volumenya turun saat ada suara dub (auto-ducking).

    ✅ File bisa diputar di browser & mobile.