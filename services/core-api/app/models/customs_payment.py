import uuid
from enum import Enum as PyEnum
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Date, ForeignKey, DateTime, DECIMAL, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class PaymentType(str, PyEnum):
    DUTY = "duty"
    VAT = "vat"
    EXCISE = "excise"
    CUSTOMS_FEE = "customs_fee"
    SPOT_VAT = "spot_vat"
    SPOT_EXCISE = "spot_excise"


class CustomsPayment(Base):
    __tablename__ = "customs_payments"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declarations.id"), nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declaration_items.id"), nullable=True
    )
    payment_type: Mapped[str] = mapped_column(String(20))
    payment_type_code: Mapped[Optional[str]] = mapped_column(String(4))
    payment_specifics: Mapped[Optional[str]] = mapped_column(String(2))
    base_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    rate: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 4))
    amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    calc_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tax_base_currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    tax_base_unit_code: Mapped[Optional[str]] = mapped_column(String(4))
    rate_type_code: Mapped[Optional[str]] = mapped_column(String(1))
    rate_currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    rate_unit_code: Mapped[Optional[str]] = mapped_column(String(4))
    weighting_factor: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(19, 6))
    rate_use_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    declaration: Mapped["Declaration"] = relationship(
        "Declaration", back_populates="payments"
    )
    item: Mapped[Optional["DeclarationItem"]] = relationship(
        "DeclarationItem", back_populates="payments"
    )
