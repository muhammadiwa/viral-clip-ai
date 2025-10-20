"""SQLAlchemy model for DMCA notices."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class DmcaNoticeModel(Base):
    """Stores DMCA takedown requests for compliance review."""

    __tablename__ = "dmca_notices"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=False
    )
    reporter_name: Mapped[str] = mapped_column(String(160), nullable=False)
    reporter_email: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=True
    )
    infringing_material_description: Mapped[str] = mapped_column(
        String(2000), nullable=False
    )
    original_material_description: Mapped[str] = mapped_column(
        String(2000), nullable=False
    )
    additional_details: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    signature: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    action_taken: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
