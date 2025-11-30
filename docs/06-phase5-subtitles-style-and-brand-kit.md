# 06 – Phase 5: Subtitles, Styles & Brand Kit

## 1. Goal

- Generate subtitle per clip.
- Simpan segment subtitle.
- Menyediakan beberapa preset subtitle style.
- Menambahkan brand kit per user (logo, warna).

## 2. Data Model

### 2.1. SubtitleSegment

Tabel: `subtitle_segments`

- `id`
- `clip_id`
- `start_time_sec`
- `end_time_sec`
- `text`
- `language`
- `created_at`

### 2.2. SubtitleStyle

Tabel: `subtitle_styles`

- `id`
- `user_id | NULL` (NULL = global preset)
- `name`
- `style_json`:
  - `font_family`
  - `font_weight`
  - `font_size`
  - `text_color`
  - `stroke_color`
  - `stroke_width`
  - `shadow`
  - `background_color`
  - `position` (`top`, `middle`, `bottom`)
  - `animation` (`fade`, `pop`, `none`)
- `is_default_global: bool`

### 2.3. BrandKit

Tabel: `brand_kits`

- `id`
- `user_id`
- `name`
- `logo_path`
- `primary_color`
- `secondary_color`
- `default_subtitle_style_id`
- `watermark_position` (`top-left`, dll)

## 3. Subtitle Generation Pipeline

Untuk tiap clip:

1. Ambil transcript terkait (dari `transcript_segments` dengan range waktu clip).
2. Bagi menjadi kalimat pendek 1–2 baris.
3. Hitung timestamp per kalimat (proporsi).
4. Simpan ke `subtitle_segments`.

Untuk multi-bahasa:

- Tambah endpoint:
  - `POST /viral-clip/clips/{id}/subtitles/translate`
  - Body: `target_language`.
- Motor translate: LLM (Responses API) dengan mode terstruktur (input sentence, output translation).

## 4. Endpoint

### 4.1. GET /viral-clip/clips/{id}/subtitles

Return list subtitle segments.

### 4.2. GET /subtitle-styles

Return daftar style global + milik user.

### 4.3. POST /subtitle-styles

Create style custom user.

### 4.4. GET /brand-kit

Return brand kit user (1 saja).

### 4.5. POST /brand-kit

Create/update brand kit (logo upload, warna, default style).

## 5. Frontend Impact

- Section **Subtitle Style** di halaman AI Clipping mengambil data dari `/subtitle-styles`.
- Brand kit mempengaruhi:
  - Default subtitle style.
  - Logo/watermark overlay saat export (phase 6).

## 6. Testing Checklist

- ✅ Subtitle muncul konsisten dengan transcript & timing.
- ✅ Preset style bisa diambil & di-select.
- ✅ Brand kit bisa disimpan & dibaca ulang.