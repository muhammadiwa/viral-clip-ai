import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.session import engine, SessionLocal
from app import models  # noqa: F401 - ensure metadata is registered
from app.api.routes import (
    health,
    auth,
    viral_clip_videos,
    viral_clip_batches,
    viral_clip_clips,
    subtitles,
    subtitle_styles,
    brand_kit,
    exports,
    jobs,
    audio,
)
from app.models import SubtitleStyle

settings = get_settings()

# Basic structured logging to stdout for ops visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure media directory exists before mounting
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(viral_clip_videos.router, prefix="/api")
app.include_router(viral_clip_batches.router, prefix="/api")
app.include_router(viral_clip_clips.router, prefix="/api")
app.include_router(subtitles.router, prefix="/api")
app.include_router(subtitle_styles.router, prefix="/api")
app.include_router(brand_kit.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(audio.router, prefix="/api")


def seed_defaults():
    """Seed global subtitle styles so the UI has presets to pick from."""
    db = SessionLocal()
    try:
        if not db.query(SubtitleStyle).filter(SubtitleStyle.is_default_global.is_(True)).first():
            presets = [
                SubtitleStyle(
                    user_id=None,
                    name="Bold Pop",
                    is_default_global=True,
                    style_json={
                        "font_family": "Sora",
                        "font_weight": "700",
                        "font_size": 22,
                        "text_color": "#ffffff",
                        "stroke_color": "#111827",
                        "stroke_width": 3,
                        "shadow": True,
                        "background_color": "#11182780",
                        "position": "bottom",
                        "animation": "pop",
                    },
                ),
                SubtitleStyle(
                    user_id=None,
                    name="Minimal Clean",
                    is_default_global=True,
                    style_json={
                        "font_family": "Inter",
                        "font_weight": "600",
                        "font_size": 20,
                        "text_color": "#111827",
                        "stroke_color": "#f8fafc",
                        "stroke_width": 2,
                        "shadow": False,
                        "background_color": "#ffffffb3",
                        "position": "bottom",
                        "animation": "fade",
                    },
                ),
                SubtitleStyle(
                    user_id=None,
                    name="Cinematic",
                    is_default_global=True,
                    style_json={
                        "font_family": "Space Grotesk",
                        "font_weight": "700",
                        "font_size": 24,
                        "text_color": "#f1f5f9",
                        "stroke_color": "#0f172a",
                        "stroke_width": 4,
                        "shadow": True,
                        "background_color": "#0f172a90",
                        "position": "middle",
                        "animation": "pop",
                    },
                ),
            ]
            db.add_all(presets)
            db.commit()
    finally:
        db.close()


seed_defaults()
