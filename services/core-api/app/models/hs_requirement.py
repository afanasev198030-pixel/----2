import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class HsRequirement(Base):
    __tablename__ = "hs_requirements"
    __table_args__ = (
        Index("idx_hs_requirements_prefix", "hs_code_prefix"),
        Index("idx_hs_requirements_type", "requirement_type"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    hs_code_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    legal_basis: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
