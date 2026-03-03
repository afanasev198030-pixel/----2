"""
API для истории кодов ТН ВЭД по контрагентам (Phase 1.5).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.hs_code_history import HsCodeHistory

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/hs-history", tags=["hs-history"])


class HsHistoryItem(BaseModel):
    id: str
    hs_code: str
    description: str
    counterparty_name: Optional[str]
    usage_count: int
    source: str
    created_at: Optional[str]

    model_config = {"from_attributes": True}


@router.get("")
async def get_hs_history(
    counterparty_id: Optional[uuid.UUID] = None,
    q: Optional[str] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История кодов ТН ВЭД для компании текущего пользователя."""
    query = select(HsCodeHistory).where(
        HsCodeHistory.company_id == current_user.company_id
    )

    if counterparty_id:
        query = query.where(HsCodeHistory.counterparty_id == counterparty_id)

    if q:
        query = query.where(
            HsCodeHistory.description.ilike(f"%{q}%")
            | HsCodeHistory.hs_code.ilike(f"%{q}%")
            | HsCodeHistory.counterparty_name.ilike(f"%{q}%")
        )

    query = query.order_by(HsCodeHistory.usage_count.desc(), HsCodeHistory.updated_at.desc()).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()
    return [
        HsHistoryItem(
            id=str(h.id),
            hs_code=h.hs_code,
            description=h.description[:200],
            counterparty_name=h.counterparty_name,
            usage_count=h.usage_count,
            source=h.source,
            created_at=h.created_at.isoformat() if h.created_at else None,
        )
        for h in items
    ]


@router.get("/suggest")
async def suggest_hs_code(
    description: str = Query(..., min_length=3),
    counterparty_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подсказка кода ТН ВЭД из истории по описанию товара."""
    desc_norm = description[:300].strip().lower()

    query = select(HsCodeHistory).where(
        HsCodeHistory.company_id == current_user.company_id,
    )

    if counterparty_id:
        query = query.where(HsCodeHistory.counterparty_id == counterparty_id)

    try:
        query = query.where(
            sa_func.similarity(HsCodeHistory.description_trgm, desc_norm) > 0.25
        ).order_by(
            sa_func.similarity(HsCodeHistory.description_trgm, desc_norm).desc(),
            HsCodeHistory.usage_count.desc(),
        ).limit(5)

        result = await db.execute(query)
        items = result.scalars().all()
    except Exception:
        query = select(HsCodeHistory).where(
            HsCodeHistory.company_id == current_user.company_id,
            HsCodeHistory.description.ilike(f"%{desc_norm[:30]}%"),
        ).order_by(HsCodeHistory.usage_count.desc()).limit(5)
        result = await db.execute(query)
        items = result.scalars().all()

    return [
        {
            "hs_code": h.hs_code,
            "description": h.description[:150],
            "counterparty_name": h.counterparty_name,
            "usage_count": h.usage_count,
            "source": "history",
        }
        for h in items
    ]
