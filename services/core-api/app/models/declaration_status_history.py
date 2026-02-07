import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class DeclarationStatusHistory(Base):
    __tablename__ = "declaration_status_history"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    declaration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("core.declarations.id"), nullable=False
    )
    status_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status_text: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="system")
    customs_post_code: Mapped[Optional[str]] = mapped_column(String(8))
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    declaration: Mapped["Declaration"] = relationship(
        "Declaration", back_populates="status_history"
    )
