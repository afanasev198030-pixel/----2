import uuid
from typing import Optional
from datetime import datetime, date
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Date, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class BrokerClient(Base):
    __tablename__ = "broker_clients"
    __table_args__ = (
        UniqueConstraint(
            "broker_company_id", "client_company_id", name="uq_broker_client"
        ),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    broker_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=False
    )
    client_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=False
    )
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))
    contract_date: Mapped[Optional[date]] = mapped_column(Date)
    tariff_plan: Mapped[Optional[str]] = mapped_column(
        String(50), server_default="standard"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    broker_company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[broker_company_id], lazy="selectin"
    )
    client_company: Mapped["Company"] = relationship(
        "Company", foreign_keys=[client_company_id], lazy="selectin"
    )


class UserCompanyAccess(Base):
    __tablename__ = "user_company_access"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=False
    )
    access_level: Mapped[Optional[str]] = mapped_column(
        String(20), server_default="full"
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
