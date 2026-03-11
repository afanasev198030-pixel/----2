import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime, date
from sqlalchemy import (
    String,
    Boolean,
    Text,
    Numeric,
    ForeignKey,
    DateTime,
    Date,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class CustomsValueDeclaration(Base):
    """ДТС-1 — декларация таможенной стоимости (метод 1, стоимость сделки)."""

    __tablename__ = "customs_value_declarations"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.declarations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    form_type: Mapped[str] = mapped_column(String(4), default="DTS1")

    # Графа 7 — взаимосвязь продавца и покупателя
    related_parties: Mapped[bool] = mapped_column(Boolean, default=False)
    related_price_impact: Mapped[bool] = mapped_column(Boolean, default=False)
    related_verification: Mapped[bool] = mapped_column(Boolean, default=False)

    # Графа 8 — ограничения и условия
    restrictions: Mapped[bool] = mapped_column(Boolean, default=False)
    price_conditions: Mapped[bool] = mapped_column(Boolean, default=False)

    # Графа 9 — интеллектуальная собственность
    ip_license_payments: Mapped[bool] = mapped_column(Boolean, default=False)
    sale_depends_on_income: Mapped[bool] = mapped_column(Boolean, default=False)
    income_to_seller: Mapped[bool] = mapped_column(Boolean, default=False)

    # Графа 6 — документы к графам 7–9
    additional_docs: Mapped[Optional[str]] = mapped_column(Text)

    # Графа 17 — перевозчик, место «до»; графа 25б — курс USD
    transport_carrier_name: Mapped[Optional[str]] = mapped_column(String(200))
    transport_destination: Mapped[Optional[str]] = mapped_column(String(200))
    usd_exchange_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 6))

    # Дополнительные данные
    additional_data: Mapped[Optional[str]] = mapped_column(Text)

    # Графа 10б — сведения о заполнившем
    filler_name: Mapped[Optional[str]] = mapped_column(String(200))
    filler_date: Mapped[Optional[date]] = mapped_column(Date)
    filler_document: Mapped[Optional[str]] = mapped_column(String(200))
    filler_contacts: Mapped[Optional[str]] = mapped_column(String(200))
    filler_position: Mapped[Optional[str]] = mapped_column(String(200))

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    declaration: Mapped["Declaration"] = relationship(
        "Declaration", back_populates="customs_value_declaration"
    )
    items: Mapped[list["CustomsValueItem"]] = relationship(
        "CustomsValueItem",
        back_populates="customs_value_declaration",
        cascade="all, delete-orphan",
        order_by="CustomsValueItem.item_no",
    )
