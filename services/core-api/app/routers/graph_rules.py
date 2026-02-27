"""
API для управления правилами заполнения граф ДТ.
Позволяет: просматривать, редактировать, массово импортировать правила.
"""
from typing import Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.graph_rule import DeclarationGraphRule

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/graph-rules", tags=["graph-rules"])


# ── Pydantic-схемы ────────────────────────────────────────────────────────────

class GraphRuleBase(BaseModel):
    graph_number: int
    graph_name: str
    section: str = "header"
    declaration_type: str = "IM40"
    fill_instruction: str = ""
    fill_format: str = ""
    ai_rule: str = ""
    is_required: bool = False
    skip: bool = False
    requires_document: bool = False
    default_value: Optional[str] = None
    default_flag: Optional[str] = None
    compute_expression: Optional[str] = None
    validation_rules: dict = {}
    source_priority: list = []
    source_fields: dict = {}
    confidence_map: dict = {}
    conflict_check: Optional[str] = None
    target_field: Optional[str] = None
    target_kind: Optional[str] = None
    is_active: bool = True
    version: str = "3.0"


class GraphRuleCreate(GraphRuleBase):
    pass


class GraphRuleUpdate(BaseModel):
    """Все поля опциональны — можно обновлять частично."""
    graph_name: Optional[str] = None
    section: Optional[str] = None
    fill_instruction: Optional[str] = None
    fill_format: Optional[str] = None
    ai_rule: Optional[str] = None
    is_required: Optional[bool] = None
    skip: Optional[bool] = None
    requires_document: Optional[bool] = None
    default_value: Optional[str] = None
    default_flag: Optional[str] = None
    compute_expression: Optional[str] = None
    validation_rules: Optional[dict] = None
    source_priority: Optional[list] = None
    source_fields: Optional[dict] = None
    confidence_map: Optional[dict] = None
    conflict_check: Optional[str] = None
    target_field: Optional[str] = None
    target_kind: Optional[str] = None
    is_active: Optional[bool] = None
    version: Optional[str] = None


class SourceFieldsUpdate(BaseModel):
    """
    Маппинг полей источников — заполняется на втором шаге,
    когда пользователь уточняет откуда брать данные.

    Пример:
    {
      "invoice": {
        "fields": ["seller_name", "seller_address", "seller_country"],
        "notes": "Блок Seller / Shipper в верхней части инвойса"
      },
      "contract": {
        "fields": ["party_seller.name", "party_seller.address"],
        "notes": "Раздел «Стороны договора»"
      }
    }
    """
    source_priority: Optional[list] = None
    source_fields: Optional[dict[str, Any]] = None
    confidence_map: Optional[dict[str, float]] = None


class GraphRuleResponse(GraphRuleBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BulkImportItem(BaseModel):
    graph_number: int
    graph_name: str
    section: str = "header"
    fill_instruction: str = ""
    fill_format: str = ""
    ai_rule: str = ""
    is_required: bool = False
    skip: bool = False
    default_value: Optional[str] = None
    default_flag: Optional[str] = None
    compute_expression: Optional[str] = None
    validation_rules: dict = {}
    source_priority: list = []
    confidence_map: dict = {}
    target_field: Optional[str] = None
    target_kind: Optional[str] = None


class BulkImportRequest(BaseModel):
    declaration_type: str = "IM40"
    version: str = "3.0"
    rules: list[BulkImportItem]


class BulkImportResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]


# ── Эндпоинты ─────────────────────────────────────────────────────────────────

class GraphRuleInternal(BaseModel):
    """Компактное представление правила для внутренних сервисов (без UUID/datetime)."""
    graph_number: int
    graph_name: str
    section: str
    ai_rule: str
    fill_instruction: str
    source_priority: list
    source_fields: dict
    confidence_map: dict
    target_field: Optional[str]
    skip: bool
    is_required: bool

    model_config = {"from_attributes": True}


@router.get("/internal", response_model=list[GraphRuleInternal], include_in_schema=False)
async def list_graph_rules_internal(
    declaration_type: str = "IM40",
    db: AsyncSession = Depends(get_db),
):
    """Внутренний endpoint для AI-сервиса — без user-авторизации."""
    query = (
        select(DeclarationGraphRule)
        .where(
            DeclarationGraphRule.declaration_type == declaration_type,
            DeclarationGraphRule.is_active == True,
        )
        .order_by(DeclarationGraphRule.graph_number)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("", response_model=list[GraphRuleResponse])
async def list_graph_rules(
    declaration_type: str = "IM40",
    section: str = "",
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить список всех правил заполнения граф, упорядоченных по номеру графы."""
    query = (
        select(DeclarationGraphRule)
        .where(DeclarationGraphRule.declaration_type == declaration_type)
        .order_by(DeclarationGraphRule.graph_number)
    )
    if section:
        query = query.where(DeclarationGraphRule.section == section)
    if active_only:
        query = query.where(DeclarationGraphRule.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{graph_number}", response_model=GraphRuleResponse)
async def get_graph_rule(
    graph_number: int,
    declaration_type: str = "IM40",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить правило для конкретной графы."""
    result = await db.execute(
        select(DeclarationGraphRule).where(
            DeclarationGraphRule.graph_number == graph_number,
            DeclarationGraphRule.declaration_type == declaration_type,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, f"Правило для графы {graph_number} не найдено")
    return rule


@router.post("", response_model=GraphRuleResponse, status_code=201)
async def create_graph_rule(
    data: GraphRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать правило для графы."""
    existing = await db.execute(
        select(DeclarationGraphRule).where(
            DeclarationGraphRule.graph_number == data.graph_number,
            DeclarationGraphRule.declaration_type == data.declaration_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Правило для графы {data.graph_number} ({data.declaration_type}) уже существует")

    rule = DeclarationGraphRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info("graph_rule_created", graph=data.graph_number, decl_type=data.declaration_type)
    return rule


@router.put("/{graph_number}", response_model=GraphRuleResponse)
async def update_graph_rule(
    graph_number: int,
    data: GraphRuleUpdate,
    declaration_type: str = "IM40",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить правило графы (частичное обновление)."""
    result = await db.execute(
        select(DeclarationGraphRule).where(
            DeclarationGraphRule.graph_number == graph_number,
            DeclarationGraphRule.declaration_type == declaration_type,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, f"Правило для графы {graph_number} не найдено")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rule)
    logger.info("graph_rule_updated", graph=graph_number)
    return rule


@router.patch("/{graph_number}/sources", response_model=GraphRuleResponse)
async def update_source_fields(
    graph_number: int,
    data: SourceFieldsUpdate,
    declaration_type: str = "IM40",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить маппинг источников для графы.
    Используется на втором шаге — когда уточняем откуда брать данные.
    """
    result = await db.execute(
        select(DeclarationGraphRule).where(
            DeclarationGraphRule.graph_number == graph_number,
            DeclarationGraphRule.declaration_type == declaration_type,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, f"Правило для графы {graph_number} не найдено")

    if data.source_priority is not None:
        rule.source_priority = data.source_priority
    if data.source_fields is not None:
        rule.source_fields = data.source_fields
    if data.confidence_map is not None:
        rule.confidence_map = data.confidence_map
    rule.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rule)
    logger.info("graph_rule_sources_updated", graph=graph_number,
                sources=list((data.source_fields or {}).keys()))
    return rule


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_rules(
    data: BulkImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Массовый импорт правил из инструкции.
    Если правило для графы уже существует — обновляет его (upsert).
    """
    created = updated = skipped = 0
    errors: list[str] = []

    for item in data.rules:
        try:
            result = await db.execute(
                select(DeclarationGraphRule).where(
                    DeclarationGraphRule.graph_number == item.graph_number,
                    DeclarationGraphRule.declaration_type == data.declaration_type,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for field, value in item.model_dump().items():
                    setattr(existing, field, value)
                existing.declaration_type = data.declaration_type
                existing.version = data.version
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                rule = DeclarationGraphRule(
                    **item.model_dump(),
                    declaration_type=data.declaration_type,
                    version=data.version,
                )
                db.add(rule)
                created += 1
        except Exception as e:
            errors.append(f"Графа {item.graph_number}: {e}")
            skipped += 1

    await db.commit()
    logger.info("graph_rules_bulk_import", created=created, updated=updated,
                skipped=skipped, decl_type=data.declaration_type)
    return BulkImportResponse(created=created, updated=updated, skipped=skipped, errors=errors)


@router.delete("/{graph_number}")
async def delete_graph_rule(
    graph_number: int,
    declaration_type: str = "IM40",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удалить правило графы."""
    result = await db.execute(
        select(DeclarationGraphRule).where(
            DeclarationGraphRule.graph_number == graph_number,
            DeclarationGraphRule.declaration_type == declaration_type,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, f"Правило для графы {graph_number} не найдено")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "graph_number": graph_number}
