
# 10 — Roadmap (Beyond MVP)
<same content as in the single-file doc, split for clarity>

## Phase 0 — Foundations
- Repos, CI, lint/test; Dockerfiles; shared schemas.
- MinIO + Postgres + Redis baseline; API skeleton; auth; presigned upload; UI shell.
**Done when:** Login + upload + list asset.

## Phase 1 — Ingest & Transcode
- `yt-dlp`, tus/multipart uploads; FFmpeg HLS mezz + player preview.
**Done when:** Play HLS, job progress visible.

## Phase 2 — ASR + Alignment
- faster-whisper; WhisperX; word timestamps; SRT/VTT.
**Done when:** Accurate subs editable on timeline.

## Phase 3 — Clip Discovery
- Scene detect; CLIP embeddings; ranking; candidate clips + export MP4.
**Done when:** Top‑N clips playable and saved.

## Phase 4 — Subtitle Styles & Templates
- ASS styles; overlay renderer; brand kits; watermark; intro/outro.
**Done when:** Styled subs match export pixel‑perfect.

## Phase 5 — TTS / Dubbing
- Coqui/Piper; multi‑lang; volume ducking; batch synthesis.
**Done when:** Clip exported with dubbed narration.

## Phase 6 — Movie Retell
- LLM chapters + narration; scene re‑assembly; <1h export.
**Done when:** Coherent retell delivered.

## Phase 7 — SaaS Hardening
- Plans, metering, limits; billing; RBAC; audit; admin dashboards.
**Done when:** Limits enforced; upgrade unlocks promptly.

## Phase 8 — Scale & Polish
- GPU autoscale; CDN; A/B subtitle presets; template marketplace.
**Done when:** SLOs hit at target load.
