"""
Модели базы знаний: статьи по классификации и чек-листы.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        Index("ix_knowledge_category", "category"),
        {"schema": "core"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    category = Column(String(100), nullable=False, default="general")
    tags = Column(JSONB, default=list)
    hs_codes = Column(JSONB, default=list)
    is_published = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Checklist(Base):
    __tablename__ = "checklists"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(300), nullable=False)
    description = Column(Text, default="")
    declaration_type = Column(String(10), default="IM40")
    items = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
