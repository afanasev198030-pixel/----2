import uuid
from typing import Optional
from sqlalchemy import String, Boolean, Index, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class Classifier(Base):
    __tablename__ = "classifiers"
    __table_args__ = (
        Index("idx_classifier_type_code", "classifier_type", "code"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    classifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(500))
    name_en: Mapped[Optional[str]] = mapped_column(String(500))
    parent_code: Mapped[Optional[str]] = mapped_column(String(20))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
