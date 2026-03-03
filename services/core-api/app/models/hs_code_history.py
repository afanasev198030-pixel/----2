"""
История применённых кодов ТН ВЭД по контрагентам.
Используется для автозаполнения повторных позиций (Phase 1.5).
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, DateTime, Integer, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class HsCodeHistory(Base):
    __tablename__ = "hs_code_history"
    __table_args__ = (
        Index("ix_hsh_company_desc", "company_id", "description_trgm"),
        Index("ix_hsh_counterparty", "counterparty_id"),
        Index("ix_hsh_hs_code", "hs_code"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=False
    )
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.counterparties.id"), nullable=True
    )
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_trgm: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True,
        comment="Normalized description for pg_trgm similarity search",
    )
    hs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    declaration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declarations.id"), nullable=True
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), default="ai")
    confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
