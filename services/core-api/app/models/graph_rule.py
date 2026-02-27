"""
Модель правил заполнения граф ДТ (декларации на товары).
Каждая строка — одна графа, содержит:
  - официальное описание (из инструкции по заполнению)
  - правила для AI (источники, confidence, валидация)
  - маппинг полей источников (заполняется позже)
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base


class DeclarationGraphRule(Base):
    __tablename__ = "declaration_graph_rules"
    __table_args__ = (
        UniqueConstraint("graph_number", "declaration_type", name="uq_graph_decl_type"),
        Index("ix_graph_rules_section", "section"),
        Index("ix_graph_rules_decl_type", "declaration_type"),
        Index("ix_graph_rules_number", "graph_number"),
        {"schema": "core"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Идентификаторы графы
    graph_number = Column(Integer, nullable=False)
    graph_name = Column(String(300), nullable=False)
    # Раздел: header / item / payment / other
    section = Column(String(30), nullable=False, default="header")
    # Тип декларации: IM40, EX10 и т.д.
    declaration_type = Column(String(20), nullable=False, default="IM40")

    # Официальное описание графы (из нормативной инструкции)
    fill_instruction = Column(Text, nullable=False, default="")
    # Формат значения (если есть требования к формату)
    fill_format = Column(Text, default="")
    # Специальное правило для AI
    ai_rule = Column(Text, default="")

    # Флаги поведения
    is_required = Column(Boolean, default=False)
    skip = Column(Boolean, default=False)          # графа 13 — не заполняется
    requires_document = Column(Boolean, default=False)

    # Значение по умолчанию и флаг "проверьте"
    default_value = Column(String(500), nullable=True)
    default_flag = Column(String(200), nullable=True)

    # Вычисляемое выражение (если значение считается автоматически)
    compute_expression = Column(Text, nullable=True)

    # Правила валидации: { type, min, max, values, pattern, ... }
    validation_rules = Column(JSONB, default=dict)

    # Приоритет источников: ["invoice", "contract", ...]
    # Уточняется пользователем на втором шаге
    source_priority = Column(JSONB, default=list)

    # Маппинг полей из источников:
    # { "invoice": { "fields": ["seller_name", "seller_address"], "notes": "..." } }
    # Заполняется на втором шаге — когда пользователь уточняет откуда брать данные
    source_fields = Column(JSONB, default=dict)

    # Confidence по источнику: { "invoice": 0.8, "contract": 0.9 }
    confidence_map = Column(JSONB, default=dict)

    # Описание проверки конфликтов между источниками
    conflict_check = Column(Text, nullable=True)

    # Целевое поле в схеме core-api (из YAML target.field)
    target_field = Column(String(200), nullable=True)
    target_kind = Column(String(50), nullable=True)

    # Мета
    is_active = Column(Boolean, default=True)
    version = Column(String(20), default="3.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
