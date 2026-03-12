import uuid
from typing import Optional
from datetime import datetime, date
from sqlalchemy import String, Integer, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class DeclarationItemDocument(Base):
    """Представленный документ (графа 44 ДТ), привязанный к товарной позиции."""

    __tablename__ = "declaration_item_documents"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.declaration_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_kind_code: Mapped[str] = mapped_column(String(5), nullable=False)
    doc_number: Mapped[Optional[str]] = mapped_column(String(50))
    doc_date: Mapped[Optional[date]] = mapped_column(Date)
    doc_validity_date: Mapped[Optional[date]] = mapped_column(Date)
    authority_name: Mapped[Optional[str]] = mapped_column(String(300))
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    edoc_code: Mapped[Optional[str]] = mapped_column(String(10))
    archive_doc_id: Mapped[Optional[str]] = mapped_column(String(36))
    line_id: Mapped[Optional[str]] = mapped_column(String(40))
    presenting_kind_code: Mapped[Optional[str]] = mapped_column(String(1))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    item: Mapped["DeclarationItem"] = relationship(
        "DeclarationItem", back_populates="item_documents"
    )
