# 01 – Architecture & Tech Stack

Komponen:
- Frontend React (Vite + TS + Tailwind + Framer Motion).
- Backend FastAPI + SQLite + SQLAlchemy.
- Worker Python untuk proses berat (ffmpeg, AI call).
- Penyimpanan file lokal (MEDIA_ROOT).

Model kunci:
- User, AIUsageLog.
- VideoSource, ProcessingJob.
- TranscriptSegment, SceneSegment.
- ClipBatch, Clip.
- SubtitleSegment, SubtitleStyle, BrandKit.
- AudioConfig, ExportJob.
