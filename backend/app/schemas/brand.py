from typing import Optional

from pydantic import BaseModel, ConfigDict


class BrandKitCreate(BaseModel):
    name: str = "Default"
    primary_color: Optional[str] = "#ff6a00"
    secondary_color: Optional[str] = "#111827"
    logo_path: Optional[str] = None
    default_subtitle_style_id: Optional[int] = None
    watermark_position: str = "bottom-right"


class BrandKitOut(BrandKitCreate):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
