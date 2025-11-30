from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, ConfigDict


class SubtitleSegmentOut(BaseModel):
    id: int
    clip_id: int
    start_time_sec: float
    end_time_sec: float
    text: str
    language: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubtitleStyleCreate(BaseModel):
    name: str
    style_json: Dict[str, Any]


class SubtitleStyleOut(SubtitleStyleCreate):
    id: int
    user_id: Optional[int] = None
    is_default_global: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubtitleListResponse(BaseModel):
    items: List[SubtitleSegmentOut]
