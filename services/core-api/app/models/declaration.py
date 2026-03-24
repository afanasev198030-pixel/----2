import uuid
from enum import Enum as PyEnum
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    Date,
    DECIMAL,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class DeclarationStatus(str, PyEnum):
    NEW = "new"
    REQUIRES_ATTENTION = "requires_attention"
    READY_TO_SEND = "ready_to_send"
    SENT = "sent"


class ProcessingStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    AUTO_FILLED = "auto_filled"
    PROCESSING_ERROR = "processing_error"


class SignatureStatus(str, PyEnum):
    UNSIGNED = "unsigned"
    SIGNED = "signed"


class SpotStatus(str, PyEnum):
    NONE = "none"
    REQUIRED = "required"
    CREATED = "created"
    PAID = "paid"
    QR_RECEIVED = "qr_received"


class Declaration(Base):
    __tablename__ = "declarations"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    number_internal: Mapped[Optional[str]] = mapped_column(String(50))
    type_code: Mapped[Optional[str]] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="new")
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=False
    )
    sender_counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.counterparties.id"), nullable=True
    )
    receiver_counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.counterparties.id"), nullable=True
    )
    financial_counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.counterparties.id"), nullable=True
    )
    declarant_counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.counterparties.id"), nullable=True
    )
    country_dispatch_code: Mapped[Optional[str]] = mapped_column(String(2))
    country_origin_name: Mapped[Optional[str]] = mapped_column(String(60))
    country_destination_code: Mapped[Optional[str]] = mapped_column(String(2))
    transport_at_border: Mapped[Optional[str]] = mapped_column(String(100))
    container_info: Mapped[Optional[str]] = mapped_column(String(1))
    incoterms_code: Mapped[Optional[str]] = mapped_column(String(3))
    transport_on_border: Mapped[Optional[str]] = mapped_column(String(100))
    currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    total_invoice_value: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    exchange_rate: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 6))
    deal_nature_code: Mapped[Optional[str]] = mapped_column(String(3))
    transport_type_border: Mapped[Optional[str]] = mapped_column(String(2))
    transport_type_inland: Mapped[Optional[str]] = mapped_column(String(2))
    loading_place: Mapped[Optional[str]] = mapped_column(String(200))
    financial_info: Mapped[Optional[str]] = mapped_column(Text)
    total_customs_value: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    total_gross_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 3))
    total_net_weight: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(12, 3))
    total_items_count: Mapped[Optional[int]] = mapped_column(Integer)
    total_packages_count: Mapped[Optional[int]] = mapped_column(Integer)
    forms_count: Mapped[Optional[int]] = mapped_column(Integer)
    specifications_count: Mapped[Optional[int]] = mapped_column(Integer)
    customs_office_code: Mapped[Optional[str]] = mapped_column(String(8))
    warehouse_name: Mapped[Optional[str]] = mapped_column(String(200))
    spot_required: Mapped[bool] = mapped_column(Boolean, default=False)
    spot_status: Mapped[str] = mapped_column(String(20), default="none")
    spot_qr_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    spot_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Task Queue fields for async AI processing
    ai_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), default="not_started")
    signature_status: Mapped[str] = mapped_column(String(20), default="unsigned")
    place_and_date: Mapped[Optional[str]] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id")
    )
    # Графы ДТ по офиц. форме (Решение КТС No 257)
    special_ref_code: Mapped[Optional[str]] = mapped_column(String(20))       # Графа 7
    trading_country_code: Mapped[Optional[str]] = mapped_column(String(2))    # Графа 11
    declarant_inn_kpp: Mapped[Optional[str]] = mapped_column(String(30))    # Графа 14 ИНН/КПП
    declarant_ogrn: Mapped[Optional[str]] = mapped_column(String(15))       # Графа 14 ОГРН
    declarant_phone: Mapped[Optional[str]] = mapped_column(String(20))      # Графа 14 телефон
    delivery_place: Mapped[Optional[str]] = mapped_column(String(200))      # Графа 20 город
    transport_on_border_id: Mapped[Optional[str]] = mapped_column(String(100))  # Графа 21 рейс
    entry_customs_code: Mapped[Optional[str]] = mapped_column(String(8))    # Графа 29
    goods_location: Mapped[Optional[str]] = mapped_column(Text)             # Графа 30
    deal_specifics_code: Mapped[Optional[str]] = mapped_column(String(2))     # Графа 24 подр.2
    payment_deferral: Mapped[Optional[str]] = mapped_column(String(500))      # Графа 48
    warehouse_requisites: Mapped[Optional[str]] = mapped_column(String(500))  # Графа 49
    transit_offices: Mapped[Optional[str]] = mapped_column(Text)              # Графа 51
    destination_office_code: Mapped[Optional[str]] = mapped_column(String(100))  # Графа 53
    country_first_destination_code: Mapped[Optional[str]] = mapped_column(String(2))  # Графа 10
    guarantee_info: Mapped[Optional[str]] = mapped_column(String(500))              # Графа 52
    freight_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 2))
    freight_currency: Mapped[Optional[str]] = mapped_column(String(3))
    signatory_name: Mapped[Optional[str]] = mapped_column(String(200))
    signatory_position: Mapped[Optional[str]] = mapped_column(String(200))
    signatory_id_doc: Mapped[Optional[str]] = mapped_column(String(200))
    signatory_cert_number: Mapped[Optional[str]] = mapped_column(String(20))
    signatory_power_of_attorney: Mapped[Optional[str]] = mapped_column(String(200))
    broker_registry_number: Mapped[Optional[str]] = mapped_column(String(30))
    broker_contract_number: Mapped[Optional[str]] = mapped_column(String(50))
    broker_contract_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # ДТС графы 4–5: инвойс и контракт
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    transport_reg_number: Mapped[Optional[str]] = mapped_column(String(50))
    transport_nationality_code: Mapped[Optional[str]] = mapped_column(String(2))
    goods_location_code: Mapped[Optional[str]] = mapped_column(String(2))
    goods_location_customs_code: Mapped[Optional[str]] = mapped_column(String(8))
    goods_location_zone_id: Mapped[Optional[str]] = mapped_column(String(50))
    goods_location_info_type_code: Mapped[Optional[str]] = mapped_column(String(2))
    goods_location_svh_doc_id: Mapped[Optional[str]] = mapped_column(String(100))
    goods_location_address: Mapped[Optional[str]] = mapped_column(Text)
    border_customs_name: Mapped[Optional[str]] = mapped_column(String(200))
    border_customs_country_code: Mapped[Optional[str]] = mapped_column(String(3))
    transport_kind_code: Mapped[Optional[str]] = mapped_column(String(3))
    transport_type_name: Mapped[Optional[str]] = mapped_column(String(200))
    transport_means_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    signatory_surname: Mapped[Optional[str]] = mapped_column(String(100))
    signatory_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    signatory_middle_name: Mapped[Optional[str]] = mapped_column(String(100))
    signatory_phone: Mapped[Optional[str]] = mapped_column(String(20))
    signatory_email: Mapped[Optional[str]] = mapped_column(String(100))
    signatory_id_card_code: Mapped[Optional[str]] = mapped_column(String(10))
    signatory_id_card_series: Mapped[Optional[str]] = mapped_column(String(10))
    signatory_id_card_number: Mapped[Optional[str]] = mapped_column(String(10))
    signatory_id_card_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signatory_id_card_org: Mapped[Optional[str]] = mapped_column(String(200))
    signatory_poa_number: Mapped[Optional[str]] = mapped_column(String(50))
    signatory_poa_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signatory_poa_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signatory_poa_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    signatory_signing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    broker_doc_kind_code: Mapped[Optional[str]] = mapped_column(String(5))
    broker_contract_doc_kind_code: Mapped[Optional[str]] = mapped_column(String(5))

    evidence_map: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment='{"field_name": {"source": "invoice", "document_id": "...", "confidence": 0.95, "raw_value": "..."}}',
    )
    ai_issues: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment='[{"code": "MISSING_FIELD", "severity": "error", "field": "hs_code", "blocking": true, "message": "...", "source": "ai"}]',
    )
    ai_confidence: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(3, 2), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="declarations")
    sender_counterparty: Mapped[Optional["Counterparty"]] = relationship(
        "Counterparty",
        back_populates="declarations_as_sender",
        foreign_keys=[sender_counterparty_id],
    )
    receiver_counterparty: Mapped[Optional["Counterparty"]] = relationship(
        "Counterparty",
        back_populates="declarations_as_receiver",
        foreign_keys=[receiver_counterparty_id],
    )
    financial_counterparty: Mapped[Optional["Counterparty"]] = relationship(
        "Counterparty",
        back_populates="declarations_as_financial",
        foreign_keys=[financial_counterparty_id],
    )
    declarant_counterparty: Mapped[Optional["Counterparty"]] = relationship(
        "Counterparty",
        back_populates="declarations_as_declarant",
        foreign_keys=[declarant_counterparty_id],
    )
    created_by_user: Mapped["User"] = relationship(
        "User", back_populates="declarations", foreign_keys=[created_by]
    )
    items: Mapped[list["DeclarationItem"]] = relationship(
        "DeclarationItem", back_populates="declaration", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="declaration"
    )
    logs: Mapped[list["DeclarationLog"]] = relationship(
        "DeclarationLog", back_populates="declaration", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["DeclarationStatusHistory"]] = relationship(
        "DeclarationStatusHistory", back_populates="declaration", cascade="all, delete-orphan"
    )
    payments: Mapped[list["CustomsPayment"]] = relationship(
        "CustomsPayment", back_populates="declaration", cascade="all, delete-orphan"
    )
    customs_value_declaration: Mapped[Optional["CustomsValueDeclaration"]] = relationship(
        "CustomsValueDeclaration", back_populates="declaration", uselist=False,
        cascade="all, delete-orphan",
    )
