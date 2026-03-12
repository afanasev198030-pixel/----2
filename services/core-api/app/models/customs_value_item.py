import uuid
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Integer,
    ForeignKey,
    DateTime,
    DECIMAL,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class CustomsValueItem(Base):
    """Строка расчёта ДТС-1 по конкретному товару (второй лист, до 3 на лист)."""

    __tablename__ = "customs_value_items"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customs_value_declaration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.customs_value_declarations.id", ondelete="CASCADE"),
        nullable=False,
    )
    declaration_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.declaration_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    item_no: Mapped[int] = mapped_column(Integer, nullable=False)
    hs_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Графа 11 — цена сделки
    invoice_price_foreign: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    invoice_price_national: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    # Графа 11б — косвенные платежи
    indirect_payments: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    # Графа 12 — итого основа = 11а(нац.) + 11б
    base_total: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))

    # --- Дополнительные начисления (графы 13–19) ---
    broker_commission: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    packaging_cost: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    raw_materials: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    tools_molds: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    consumed_materials: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    design_engineering: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    license_payments: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    seller_income: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    transport_cost: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    loading_unloading: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    insurance_cost: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    # Графа 20 — итого начислений = sum(13..19)
    additions_total: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )

    # --- Вычеты (графы 21–23) ---
    construction_after_import: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    inland_transport: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    duties_taxes: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )
    # Графа 24 — итого вычетов = 21 + 22 + 23
    deductions_total: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(15, 2), default=0
    )

    # Графа 25 — таможенная стоимость
    customs_value_national: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    customs_value_usd: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))

    # Графа * — пересчёт валют (JSONB массив)
    currency_conversions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    customs_value_declaration: Mapped["CustomsValueDeclaration"] = relationship(
        "CustomsValueDeclaration", back_populates="items"
    )
    declaration_item: Mapped["DeclarationItem"] = relationship("DeclarationItem")
