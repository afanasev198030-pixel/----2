import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(12), unique=True)
    kpp: Mapped[Optional[str]] = mapped_column(String(9))
    ogrn: Mapped[Optional[str]] = mapped_column(String(15))
    address: Mapped[Optional[str]] = mapped_column(Text)
    country_code: Mapped[Optional[str]] = mapped_column(String(2))
    company_type: Mapped[Optional[str]] = mapped_column(
        String(20), server_default="client"
    )
    broker_license: Mapped[Optional[str]] = mapped_column(String(50))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="company"
    )
    counterparties: Mapped[list["Counterparty"]] = relationship(
        "Counterparty", back_populates="company"
    )
    declarations: Mapped[list["Declaration"]] = relationship(
        "Declaration", back_populates="company"
    )
