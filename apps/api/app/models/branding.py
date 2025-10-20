"""SQLAlchemy model for brand kits."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base
from ..domain.branding import BrandAssetKind


class BrandKitModel(Base):
    __tablename__ = "brand_kits"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subtitle_preset: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subtitle_overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    watermark_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    intro_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    outro_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    assets = relationship(
        "BrandAssetModel", back_populates="brand_kit", cascade="all, delete-orphan"
    )


class BrandAssetModel(Base):
    __tablename__ = "brand_kit_assets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    brand_kit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brand_kits.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[BrandAssetKind] = mapped_column(
        SAEnum(BrandAssetKind), nullable=False, default=BrandAssetKind.OTHER
    )
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )

    brand_kit = relationship("BrandKitModel", back_populates="assets")
