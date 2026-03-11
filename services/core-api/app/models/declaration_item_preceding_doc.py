import uuid
from typing import Optional
from datetime import datetime, date
from sqlalchemy import String, Integer, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class DeclarationItemPrecedingDoc(Base):
    """Предшествующий документ (графа 40 ДТ), привязанный к товарной позиции."""

    __tablename__ = "declaration_item_preceding_docs"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.declaration_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_kind_code: Mapped[Optional[str]] = mapped_column(String(5))
    doc_name: Mapped[Optional[str]] = mapped_column(String(250))
    customs_office_code: Mapped[Optional[str]] = mapped_column(String(8))
    doc_date: Mapped[Optional[date]] = mapped_column(Date)
    customs_doc_number: Mapped[Optional[str]] = mapped_column(String(7))
    other_doc_number: Mapped[Optional[str]] = mapped_column(String(50))
    other_doc_date: Mapped[Optional[date]] = mapped_column(Date)
    goods_number: Mapped[Optional[int]] = mapped_column(Integer)
    line_id: Mapped[Optional[str]] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    item: Mapped["DeclarationItem"] = relationship(
        "DeclarationItem", back_populates="preceding_docs"
    )
