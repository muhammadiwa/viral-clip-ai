from functools import lru_cache
from secrets import token_urlsafe
from typing import List

from pydantic import AnyHttpUrl, BaseSettings, Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    api_v1_prefix: str = "/v1"
    project_name: str = "Viral Clip AI API"
    cors_origins: List[AnyHttpUrl] = []
    default_org_id: str | None = None
    secret_key: str = Field(default_factory=lambda: token_urlsafe(32))
    access_token_expire_minutes: int = 60
    rate_limit_requests_per_minute: int = Field(default=120, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    subscription_trial_days: int = Field(default=14, ge=0)
    subscription_cycle_days: int = Field(default=30, ge=1)

    database_url: str | None = Field(
        default=None,
        description="SQLAlchemy connection string for the primary Postgres database",
    )

    redis_url: str | None = Field(
        default=None,
        description="Redis connection string used for rate limiting and task queues",
    )

    celery_broker_url: str | None = Field(
        default=None,
        description="Broker URL for Celery workers; falls back to Redis when unset",
    )
    celery_result_backend: str | None = Field(
        default=None,
        description="Result backend for Celery; defaults to the broker when omitted",
    )

    plan_price_free_idr: int = Field(default=0, ge=0)
    plan_price_pro_idr: int = Field(default=299_000, ge=0)
    plan_price_business_idr: int = Field(default=899_000, ge=0)

    plan_minutes_quota_free: int = Field(default=600, ge=0)
    plan_minutes_quota_pro: int = Field(default=3_000, ge=0)
    plan_minutes_quota_business: int = Field(default=10_000, ge=0)

    plan_clip_quota_free: int = Field(default=50, ge=0)
    plan_clip_quota_pro: int = Field(default=250, ge=0)
    plan_clip_quota_business: int = Field(default=1_000, ge=0)

    plan_retell_quota_free: int = Field(default=5, ge=0)
    plan_retell_quota_pro: int = Field(default=40, ge=0)
    plan_retell_quota_business: int = Field(default=120, ge=0)

    plan_storage_quota_gb_free: float = Field(default=50.0, ge=0)
    plan_storage_quota_gb_pro: float = Field(default=250.0, ge=0)
    plan_storage_quota_gb_business: float = Field(default=1024.0, ge=0)

    whisper_model_name: str = Field(default="base", description="faster-whisper model size")
    whisper_compute_type: str = Field(default="float16", description="Compute type passed to faster-whisper")
    alignment_model_name: str = Field(
        default="WAV2VEC2_ASR_BASE_960H",
        description="WhisperX alignment model identifier",
    )
    alignment_device: str | None = Field(
        default=None,
        description="Optional override for the device used during alignment (cuda/cpu)",
    )
    clip_model_name: str = Field(default="ViT-B-32", description="OpenCLIP model name")
    clip_model_pretrained: str = Field(
        default="openai", description="Pretrained weights identifier for OpenCLIP"
    )
    clip_sample_interval_seconds: int = Field(
        default=2, ge=1, description="Seconds between sampled frames during clip discovery"
    )
    clip_motion_weight: float = Field(default=0.5, ge=0)
    clip_audio_weight: float = Field(default=0.3, ge=0)
    clip_keyword_weight: float = Field(default=0.2, ge=0)
    clip_duration_weight: float = Field(default=0.15, ge=0)
    clip_confidence_bias: float = Field(default=0.25)
    clip_confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    clip_min_duration_seconds: int = Field(default=12, ge=3)
    clip_max_duration_seconds: int = Field(default=45, ge=5)
    clip_target_duration_seconds: int = Field(default=22, ge=5)
    tts_model_name: str = Field(
        default="tts_models/multilingual-multi-dataset/xtts_v2",
        description="Coqui TTS model identifier",
    )
    tts_speaker_wav: str | None = Field(
        default=None,
        description="Optional reference audio used to clone speaker characteristics",
    )
    tts_music_gain_db: float = Field(default=-9.0)
    tts_voice_gain_db: float = Field(default=-1.5)
    tts_loudness_target_i: float = Field(default=-16.0)
    tts_loudness_true_peak: float = Field(default=-1.5)
    tts_loudness_range: float = Field(default=11.0)
    retell_summary_sentences: int = Field(
        default=8, ge=1, description="Target sentence count for generated retell summaries"
    )
    export_video_preset: str = Field(
        default="veryfast",
        description="ffmpeg preset used when rendering project exports",
    )
    export_brand_intro_object_key: str | None = Field(
        default=None,
        description="Optional MinIO object key for a branded intro clip appended to exports",
    )
    export_brand_outro_object_key: str | None = Field(
        default=None,
        description="Optional MinIO object key for a branded outro clip appended to exports",
    )
    export_watermark_object_key: str | None = Field(
        default=None,
        description="Optional MinIO object key for a transparent watermark image",
    )
    export_watermark_position: str = Field(
        default="bottom-right",
        description="Preferred watermark placement (top-left, top-right, bottom-left, bottom-right)",
    )
    export_watermark_scale: float = Field(
        default=0.18,
        gt=0.0,
        le=1.0,
        description="Relative scale applied to watermark images during export",
    )
    subtitle_default_preset: str = Field(
        default="brand-kit",
        description="Preset applied when clips do not specify styling preferences",
    )
    subtitle_brand_preset_name: str = Field(
        default="brand-kit",
        description="Identifier exposed to clients for the environment-specific brand preset",
    )
    subtitle_brand_font_family: str | None = Field(
        default=None,
        description="Override font family for the brand subtitle preset",
    )
    subtitle_brand_text_color: str | None = Field(
        default=None,
        description="Primary text color for the brand subtitle preset",
    )
    subtitle_brand_background_color: str | None = Field(
        default=None,
        description="Background color for the brand subtitle preset",
    )
    subtitle_brand_stroke_color: str | None = Field(
        default=None,
        description="Stroke/outline color for the brand subtitle preset",
    )
    subtitle_brand_highlight_color: str | None = Field(
        default=None,
        description="Karaoke highlight color for the brand subtitle preset",
    )
    subtitle_brand_uppercase: bool = Field(
        default=False,
        description="Force uppercase text for the brand subtitle preset",
    )

    enable_prometheus_metrics: bool = Field(
        default=True, description="Expose Prometheus metrics endpoint when true"
    )
    prometheus_metrics_path: str = Field(
        default="/metrics/prometheus",
        description="Path where scraped Prometheus metrics are served",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP HTTP endpoint for exporting traces",
    )
    otel_exporter_otlp_headers: str | None = Field(
        default=None,
        description="Comma separated key=value pairs added to OTLP requests",
    )
    otel_service_name: str | None = Field(
        default=None, description="Optional override for OpenTelemetry service.name"
    )

    midtrans_server_key: str | None = None
    midtrans_client_key: str | None = None
    midtrans_is_production: bool = False
    midtrans_app_name: str = "Viral Clip AI"

    s3_endpoint_url: AnyHttpUrl | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    s3_secure: bool | None = None
    storage_upload_expiry_seconds: int = Field(default=900, ge=60, le=86400)

    api_base_url: AnyHttpUrl | None = Field(
        default=None,
        description="Base URL workers use when calling back into the API",
    )
    worker_service_token: str | None = Field(
        default=None,
        description="Shared secret that authenticates background workers",
    )

    worker_prometheus_port: int | None = Field(
        default=None,
        description="Optional port that exposes worker Prometheus metrics",
    )
    worker_prometheus_host: str = Field(
        default="0.0.0.0",
        description="Host interface used for worker Prometheus exporter",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
