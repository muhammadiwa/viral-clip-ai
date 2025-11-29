from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import engine
from app.db.base import Base
from app.api.routes import health, auth, viral_clip_videos, viral_clip_batches, viral_clip_clips, subtitles, brand_kit, exports

settings = get_settings()

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(viral_clip_videos.router, prefix="/api")
app.include_router(viral_clip_batches.router, prefix="/api")
app.include_router(viral_clip_clips.router, prefix="/api")
app.include_router(subtitles.router, prefix="/api")
app.include_router(brand_kit.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
