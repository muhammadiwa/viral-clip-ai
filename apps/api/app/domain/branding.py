"""Pydantic models for brand kit management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class BrandAssetKind(str, Enum):
    WATERMARK = "watermark"
    FONT = "font"
    INTRO = "intro"
    OUTRO = "outro"
    LOGO = "logo"
    OTHER = "other"


class BrandKitBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2048)
    primary_color: Optional[str] = Field(default=None, max_length=16)
    secondary_color: Optional[str] = Field(default=None, max_length=16)
    accent_color: Optional[str] = Field(default=None, max_length=16)
    font_family: Optional[str] = Field(default=None, max_length=120)
    subtitle_preset: Optional[str] = Field(default=None, max_length=80)
    subtitle_overrides: dict[str, object] = Field(default_factory=dict)
    watermark_object_key: Optional[str] = Field(default=None, max_length=512)
    intro_object_key: Optional[str] = Field(default=None, max_length=512)
    outro_object_key: Optional[str] = Field(default=None, max_length=512)
    is_default: bool = False
    is_archived: bool = False


class BrandKitCreate(BrandKitBase):
    pass


class BrandKitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2048)
    primary_color: Optional[str] = Field(default=None, max_length=16)
    secondary_color: Optional[str] = Field(default=None, max_length=16)
    accent_color: Optional[str] = Field(default=None, max_length=16)
    font_family: Optional[str] = Field(default=None, max_length=120)
    subtitle_preset: Optional[str] = Field(default=None, max_length=80)
    subtitle_overrides: Optional[dict[str, object]] = None
    watermark_object_key: Optional[str] = Field(default=None, max_length=512)
    intro_object_key: Optional[str] = Field(default=None, max_length=512)
    outro_object_key: Optional[str] = Field(default=None, max_length=512)
    is_default: Optional[bool] = None
    is_archived: Optional[bool] = None


class BrandAssetBase(BaseModel):
    label: str = Field(..., min_length=2, max_length=160)
    kind: BrandAssetKind = BrandAssetKind.OTHER


class BrandAssetCreate(BrandAssetBase):
    object_key: str = Field(..., min_length=1, max_length=512)
    uri: Optional[str] = Field(default=None, max_length=1024)


class BrandAsset(BrandAssetBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    brand_kit_id: UUID
    object_key: str
    uri: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class BrandAssetResponse(BaseModel):
    data: BrandAsset


class BrandAssetListResponse(BaseModel):
    data: list[BrandAsset]


class BrandAssetUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=200)
    content_type: Optional[str] = Field(default=None, max_length=120)
    kind: BrandAssetKind = BrandAssetKind.OTHER


class BrandAssetUploadTicket(BaseModel):
    object_key: str
    upload_url: str
    headers: dict[str, str]
    kind: BrandAssetKind


class BrandAssetUploadResponse(BaseModel):
    data: BrandAssetUploadTicket


class BrandKit(BrandKitBase):
    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    assets: list[BrandAsset] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BrandKitResponse(BaseModel):
    data: BrandKit


class BrandKitListResponse(BaseModel):
    data: list[BrandKit]
    count: int
    pagination: PaginationMeta
