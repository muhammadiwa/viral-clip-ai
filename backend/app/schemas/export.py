from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.job import ProcessingJobOut


class ExportCreate(BaseModel):
    resolution: str = "1080p"
    fps: int = 30
    aspect_ratio: str = "9:16"
    use_brand_kit: bool = True
    use_ai_dub: bool = True


class ExportOut(BaseModel):
    id: int
    clip_id: int
    resolution: str
    fps: int
    aspect_ratio: str
    status: str
    progress: float
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExportWithJob(BaseModel):
    export: ExportOut
    job: ProcessingJobOut
