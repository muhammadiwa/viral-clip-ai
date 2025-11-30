from pathlib import Path
from typing import Optional

import structlog

from app.core.config import get_settings
from app.models import AIUsageLog, Clip, AudioConfig
from app.services import utils

logger = structlog.get_logger()
settings = get_settings()


def synthesize_dub(db, clip: Clip, language: Optional[str] = None) -> str:
    """
    Generate AI dub using OpenAI TTS.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured for dubbing")
    client = utils.get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client not available")

    target_language = language or clip.language or "en"
    out_dir = Path(settings.media_root) / "audio" / "dubs" / str(clip.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"dub-{target_language}.mp3"

    script = " ".join([s.text for s in clip.subtitles]) or clip.description or clip.title or ""
    if not script:
        raise RuntimeError("No script available for dubbing")

    response = client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=settings.openai_voice,
        input=script,
    )
    response.stream_to_file(str(out_path))

    usage = getattr(response, "usage", None)
    if usage:
        db.add(
            AIUsageLog(
                user_id=clip.batch.video.user_id,
                provider="openai",
                model=settings.openai_tts_model,
                tokens_input=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_output=getattr(usage, "completion_tokens", 0) or 0,
            )
        )
    db.commit()
    logger.info("dubbing.created", clip_id=clip.id, path=str(out_path))
    return str(out_path)


def ensure_audio_config(db, clip: Clip, language: Optional[str] = None) -> AudioConfig:
    if clip.audio_config:
        return clip.audio_config
    config = AudioConfig(
        clip_id=clip.id,
        language=language or clip.language or "en",
        ai_voice_provider="openai",
        ai_voice_id=settings.openai_voice,
        mode="overlay",
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
