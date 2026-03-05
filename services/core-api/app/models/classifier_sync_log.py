import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class ClassifierSyncLog(Base):
    __tablename__ = "classifier_sync_log"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    classifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    eec_guid: Mapped[str] = mapped_column(String(40), nullable=False)
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    last_modification_check: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
