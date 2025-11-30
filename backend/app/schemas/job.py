from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProcessingJobOut(BaseModel):
    id: int
    video_source_id: Optional[int] = None
    job_type: str
    status: str
    progress: float
    payload: Optional[dict[str, Any]] = None
    result_summary: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
