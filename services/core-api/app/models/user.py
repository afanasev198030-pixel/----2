import uuid
from enum import Enum as PyEnum
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class UserRole(str, PyEnum):
    CLIENT = "client"
    VED_SPECIALIST = "ved_specialist"
    HEAD = "head"
    ACCOUNTANT = "accountant"
    LAWYER = "lawyer"
    BROKER = "broker"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.companies.id"), nullable=True
    )
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped[Optional["Company"]] = relationship(
        "Company", back_populates="users"
    )
    declarations: Mapped[list["Declaration"]] = relationship(
        "Declaration", back_populates="created_by_user"
    )
