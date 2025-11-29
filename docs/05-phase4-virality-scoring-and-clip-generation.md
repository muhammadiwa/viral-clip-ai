# 05 – Phase 4: Virality Scoring & Clip Generation

Goal:
- Menghasilkan ClipBatch dan Clip dengan skor virality.
- Menggunakan LLM (OpenAI Responses) dengan JSON schema.

Endpoint (TODO di route terpisah):
- POST /api/viral-clip/videos/{id}/clip-batches
- GET  /api/viral-clip/videos/{id}/clip-batches
- GET  /api/viral-clip/clip-batches/{batch_id}/clips
