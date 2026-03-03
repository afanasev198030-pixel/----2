"""
CRUD API для AI-стратегий (Phase 1.2).
Стратегии передаются в ai-service как дополнительные system instructions при парсинге.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.ai_strategy import AiStrategy

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ai-strategies", tags=["ai-strategies"])


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_text: str
    conditions: Optional[dict] = None
    actions: Optional[dict] = None
    priority: int = 0
    is_active: bool = True


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_text: Optional[str] = None
    conditions: Optional[dict] = None
    actions: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    rule_text: str
    conditions: Optional[dict]
    actions: Optional[dict]
    priority: int
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/internal")
async def list_active_strategies(db: AsyncSession = Depends(get_db)):
    """Internal endpoint for ai-service — no auth, returns active strategies sorted by priority."""
    result = await db.execute(
        select(AiStrategy)
        .where(AiStrategy.is_active.is_(True))
        .order_by(AiStrategy.priority.desc())
    )
    strategies = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "rule_text": s.rule_text,
            "conditions": s.conditions,
            "actions": s.actions,
            "priority": s.priority,
        }
        for s in strategies
    ]


@router.get("")
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.BROKER)),
):
    result = await db.execute(
        select(AiStrategy).order_by(AiStrategy.priority.desc(), AiStrategy.created_at.desc())
    )
    strategies = result.scalars().all()
    return [
        StrategyResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            rule_text=s.rule_text,
            conditions=s.conditions,
            actions=s.actions,
            priority=s.priority,
            is_active=s.is_active,
            created_at=s.created_at.isoformat() if s.created_at else None,
            updated_at=s.updated_at.isoformat() if s.updated_at else None,
        )
        for s in strategies
    ]


@router.post("", status_code=201)
async def create_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.BROKER)),
):
    strategy = AiStrategy(
        name=data.name,
        description=data.description,
        rule_text=data.rule_text,
        conditions=data.conditions,
        actions=data.actions,
        priority=data.priority,
        is_active=data.is_active,
        created_by=user.id,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    logger.info("ai_strategy_created", name=data.name, id=str(strategy.id))
    return {"id": str(strategy.id), "status": "created"}


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: uuid.UUID,
    data: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.BROKER)),
):
    result = await db.execute(select(AiStrategy).where(AiStrategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(strategy, field, value)

    await db.commit()
    logger.info("ai_strategy_updated", id=str(strategy_id))
    return {"status": "updated"}


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    result = await db.execute(select(AiStrategy).where(AiStrategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    await db.delete(strategy)
    await db.commit()
    logger.info("ai_strategy_deleted", id=str(strategy_id))
    return {"status": "deleted"}
