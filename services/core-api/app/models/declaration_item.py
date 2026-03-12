import uuid
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Integer,
    Text,
    ForeignKey,
    DateTime,
    DECIMAL,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class DeclarationItem(Base):
    __tablename__ = "declaration_items"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declarations.id"), nullable=False
    )
    item_no: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    package_count: Mapped[Optional[int]] = mapped_column(Integer)
    package_type: Mapped[Optional[str]] = mapped_column(String(50))
    commercial_name: Mapped[Optional[str]] = mapped_column(String(500))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(300))
    trademark: Mapped[Optional[str]] = mapped_column(String(200))
    model_name: Mapped[Optional[str]] = mapped_column(String(200))
    article_number: Mapped[Optional[str]] = mapped_column(String(100))
    hs_code: Mapped[Optional[str]] = mapped_column(String(10))
    hs_code_letters: Mapped[Optional[str]] = mapped_column(String(10))
    hs_code_extra: Mapped[Optional[str]] = mapped_column(String(4))
    country_origin_code: Mapped[Optional[str]] = mapped_column(String(2))
    country_origin_pref_code: Mapped[Optional[str]] = mapped_column(String(2))
    gross_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 3))
    preference_code: Mapped[Optional[str]] = mapped_column(String(10))
    procedure_code: Mapped[Optional[str]] = mapped_column(String(10))
    net_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 3))
    quota_info: Mapped[Optional[str]] = mapped_column(String(200))
    prev_doc_ref: Mapped[Optional[str]] = mapped_column(String(200))
    additional_unit: Mapped[Optional[str]] = mapped_column(String(20))
    additional_unit_qty: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 3))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))
    mos_method_code: Mapped[Optional[str]] = mapped_column(String(2))
    customs_value_rub: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    statistical_value_usd: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    documents_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    package_type_code: Mapped[Optional[str]] = mapped_column(String(5))
    package_marks: Mapped[Optional[str]] = mapped_column(String(500))
    additional_unit_code: Mapped[Optional[str]] = mapped_column(String(4))
    goods_marking: Mapped[Optional[str]] = mapped_column(String(200))
    serial_number: Mapped[Optional[str]] = mapped_column(String(200))
    intellect_property_sign: Mapped[Optional[str]] = mapped_column(String(1))
    goods_transfer_feature: Mapped[Optional[str]] = mapped_column(String(3))
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    declaration: Mapped["Declaration"] = relationship(
        "Declaration", back_populates="items"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="item"
    )
    payments: Mapped[list["CustomsPayment"]] = relationship(
        "CustomsPayment", back_populates="item"
    )
    item_documents: Mapped[list["DeclarationItemDocument"]] = relationship(
        "DeclarationItemDocument", back_populates="item", cascade="all, delete-orphan"
    )
    preceding_docs: Mapped[list["DeclarationItemPrecedingDoc"]] = relationship(
        "DeclarationItemPrecedingDoc", back_populates="item", cascade="all, delete-orphan"
    )
