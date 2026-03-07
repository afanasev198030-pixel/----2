import uuid
from enum import Enum as PyEnum
from typing import Optional
from datetime import datetime, date
from sqlalchemy import (
    String,
    BigInteger,
    Date,
    Text,
    ForeignKey,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class DocumentType(str, PyEnum):
    CONTRACT = "contract"
    INVOICE = "invoice"
    PACKING_LIST = "packing_list"
    TRANSPORT_DOC = "transport_doc"
    TRANSPORT_INVOICE = "transport_invoice"
    APPLICATION_STATEMENT = "application_statement"
    SPECIFICATION = "specification"
    TECH_DESCRIPTION = "tech_description"
    CERTIFICATE_ORIGIN = "certificate_origin"
    LICENSE = "license"
    PERMIT = "permit"
    SANITARY = "sanitary"
    VETERINARY = "veterinary"
    PHYTOSANITARY = "phytosanitary"
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declarations.id"), nullable=True
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declaration_items.id"), nullable=True
    )
    doc_type: Mapped[str] = mapped_column(String(30))
    file_key: Mapped[Optional[str]] = mapped_column(String(500))
    original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    issued_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(255))
    doc_number: Mapped[Optional[str]] = mapped_column(String(100))
    parsed_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    linked_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    declaration: Mapped[Optional["Declaration"]] = relationship(
        "Declaration", back_populates="documents"
    )
    item: Mapped[Optional["DeclarationItem"]] = relationship(
        "DeclarationItem", back_populates="documents"
    )
