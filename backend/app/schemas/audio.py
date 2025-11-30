from typing import Optional

from pydantic import BaseModel, ConfigDict


class AudioConfigUpdate(BaseModel):
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.25
    original_volume: float = 1.0
    ai_voice_provider: str = "openai"
    ai_voice_id: str = "alloy"
    language: str = "en"
    mode: str = "overlay"  # replace|overlay


class AudioConfigOut(AudioConfigUpdate):
    id: int
    clip_id: int

    model_config = ConfigDict(from_attributes=True)
