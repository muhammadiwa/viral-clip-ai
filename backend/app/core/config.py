from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILES = [REPO_ROOT / ".env", BACKEND_DIR / ".env"]

for env_path in ENV_FILES:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="allow")

    app_name: str = Field(default="Viral Clip AI", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")

    database_url: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    media_root: str = Field(default="media", alias="MEDIA_ROOT")
    media_base_url: str = Field(default="http://localhost:8000/media", alias="MEDIA_BASE_URL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_whisper_model: str = Field(default="whisper-1", alias="OPENAI_WHISPER_MODEL")
    openai_responses_model: str = Field(default="gpt-4o-mini", alias="OPENAI_RESPONSES_MODEL")
    openai_tts_model: str = Field(default="gpt-4o-mini-tts", alias="OPENAI_TTS_MODEL")
    openai_voice: str = Field(default="alloy", alias="OPENAI_VOICE")
    credit_cost_per_minute: int = Field(default=1, alias="CREDIT_COST_PER_MINUTE")
    credit_cost_per_export: int = Field(default=1, alias="CREDIT_COST_PER_EXPORT")

    # Upload limits
    max_upload_size_mb: int = Field(default=2048, alias="MAX_UPLOAD_SIZE_MB")
    allowed_video_types: str = Field(default="video/mp4,video/webm,video/quicktime,video/x-msvideo", alias="ALLOWED_VIDEO_TYPES")

    # Retry settings
    youtube_download_retries: int = Field(default=3, alias="YOUTUBE_DOWNLOAD_RETRIES")
    export_retries: int = Field(default=2, alias="EXPORT_RETRIES")
    retry_delay_seconds: int = Field(default=5, alias="RETRY_DELAY_SECONDS")

    # Rate limiting
    daily_job_limit: int = Field(default=50, alias="DAILY_JOB_LIMIT")

    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expires_minutes: int = Field(default=60, alias="JWT_EXPIRES_MINUTES")

    backend_cors_origins_raw: str = Field(default="http://localhost:5173", alias="BACKEND_CORS_ORIGINS")
    ffmpeg_bin: str = Field(default="ffmpeg", alias="FFMPEG_BIN")
    ffprobe_bin: str = Field(default="ffprobe", alias="FFPROBE_BIN")

    @property
    def backend_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins_raw.split(",") if origin.strip()]

    @property
    def allowed_video_types_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_video_types.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required in environment or .env")
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is required in environment or .env")
    return settings
