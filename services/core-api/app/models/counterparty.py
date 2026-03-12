import uuid
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class CounterpartyType(str, PyEnum):
    SELLER = "seller"
    BUYER = "buyer"
    IMPORTER = "importer"
    DECLARANT = "declarant"


class Counterparty(Base):
    __tablename__ = "counterparties"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    registration_number: Mapped[Optional[str]] = mapped_column(String(100))
    tax_number: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(Text)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id")
    )
    ogrn: Mapped[Optional[str]] = mapped_column(String(15))
    kpp: Mapped[Optional[str]] = mapped_column(String(9))
    postal_code: Mapped[Optional[str]] = mapped_column(String(6))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    street: Mapped[Optional[str]] = mapped_column(String(200))
    building: Mapped[Optional[str]] = mapped_column(String(20))
    room: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company", back_populates="counterparties"
    )
    declarations_as_sender: Mapped[list["Declaration"]] = relationship(
        "Declaration",
        back_populates="sender_counterparty",
        foreign_keys="[Declaration.sender_counterparty_id]",
    )
    declarations_as_receiver: Mapped[list["Declaration"]] = relationship(
        "Declaration",
        back_populates="receiver_counterparty",
        foreign_keys="[Declaration.receiver_counterparty_id]",
    )
    declarations_as_financial: Mapped[list["Declaration"]] = relationship(
        "Declaration",
        back_populates="financial_counterparty",
        foreign_keys="[Declaration.financial_counterparty_id]",
    )
    declarations_as_declarant: Mapped[list["Declaration"]] = relationship(
        "Declaration",
        back_populates="declarant_counterparty",
        foreign_keys="[Declaration.declarant_counterparty_id]",
    )
