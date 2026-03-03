"""
AI-стратегии — бизнес-правила для управления AI-заполнением деклараций.
Пример: «Если поставщик ZED Group, ставить EXW и пост Шереметьево».
Phase 1.2 roadmap.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class AiStrategy(Base):
    __tablename__ = "ai_strategies"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_text: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Текстовое бизнес-правило, передаётся в LLM как system instruction",
    )
    conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment='Структурированные условия: {"field": "supplier_name", "op": "contains", "value": "ZED"}',
    )
    actions: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment='Действия при совпадении: {"set": {"incoterms": "EXW", "customs_post": "Шереметьево"}}',
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, comment="Приоритет (выше = важнее)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
