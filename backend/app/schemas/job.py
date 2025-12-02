from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProcessingJobOut(BaseModel):
    id: int
    video_source_id: Optional[int] = None
    job_type: str
    status: str
    progress: float
    progress_message: Optional[str] = None
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    current_step_num: Optional[int] = None
    payload: Optional[dict[str, Any]] = None
    result_summary: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
