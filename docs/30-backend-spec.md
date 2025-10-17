
# 30 — Backend Spec

**Services**
- api-gateway, ingest-worker, transcode-worker, asr-worker, nlp-worker, subtitle-worker, tts-worker, render-worker, retell-worker, export-worker, billing-worker.

**Clean Architecture**
- domain (entities), repositories (DB), services (use cases), adapters (engines), routers (I/O).

**API**
- Versioned REST `/v1/*`, JWT, idempotency, pagination, webhooks, WS/SSE.

**Adapters (Strategy Pattern)**
- `AsrEngine`, `TtsEngine`, `Embedder`, `SubtitleRenderer` with concrete impls (Whisper, Coqui, CLIP, libass).
