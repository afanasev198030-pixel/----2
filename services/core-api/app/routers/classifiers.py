from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Classifier, User
from app.schemas import ClassifierResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/classifiers", tags=["classifiers"])


@router.get("/", response_model=list[ClassifierResponse])
async def list_classifiers(
    classifier_type: str = Query(..., description="Type of classifier (required)"),
    q: Optional[str] = Query(None, description="Search query"),
    parent_code: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List classifiers with filters and pagination."""
    query = select(Classifier).where(
        Classifier.classifier_type == classifier_type,
        Classifier.is_active == True,
    )
    
    conditions = []
    
    if q:
        # Search in code and name_ru
        conditions.append(
            or_(
                Classifier.code.ilike(f"%{q}%"),
                Classifier.name_ru.ilike(f"%{q}%"),
            )
        )
    
    if parent_code:
        conditions.append(Classifier.parent_code == parent_code)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(Classifier.code).offset(offset).limit(limit)
    
    result = await db.execute(query)
    classifiers = result.scalars().all()
    
    return [ClassifierResponse.model_validate(c) for c in classifiers]


@router.get("/countries", response_model=list[ClassifierResponse])
async def list_countries(
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shortcut endpoint for countries (classifier_type=country)."""
    query = select(Classifier).where(
        Classifier.classifier_type == "country",
        Classifier.is_active == True,
    )
    
    if q:
        query = query.where(
            or_(
                Classifier.code.ilike(f"%{q}%"),
                Classifier.name_ru.ilike(f"%{q}%"),
            )
        )
    
    query = query.order_by(Classifier.code)
    
    result = await db.execute(query)
    countries = result.scalars().all()
    
    return [ClassifierResponse.model_validate(c) for c in countries]


@router.get("/currencies", response_model=list[ClassifierResponse])
async def list_currencies(
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shortcut endpoint for currencies (classifier_type=currency)."""
    query = select(Classifier).where(
        Classifier.classifier_type == "currency",
        Classifier.is_active == True,
    )
    
    if q:
        query = query.where(
            or_(
                Classifier.code.ilike(f"%{q}%"),
                Classifier.name_ru.ilike(f"%{q}%"),
            )
        )
    
    query = query.order_by(Classifier.code)
    
    result = await db.execute(query)
    currencies = result.scalars().all()
    
    return [ClassifierResponse.model_validate(c) for c in currencies]


@router.get("/hs-codes/search", response_model=list[ClassifierResponse])
async def search_hs_codes(
    q: str = Query(..., description="Search query for HS code or name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search HS codes by code or name_ru. Returns top 50 results."""
    query = select(Classifier).where(
        Classifier.classifier_type == "hs_code",
        Classifier.is_active == True,
        or_(
            Classifier.code.ilike(f"%{q}%"),
            Classifier.name_ru.ilike(f"%{q}%"),
        ),
    ).order_by(Classifier.code).limit(50)
    
    result = await db.execute(query)
    hs_codes = result.scalars().all()
    
    return [ClassifierResponse.model_validate(c) for c in hs_codes]


@router.get("/hs-codes/stats")
async def hs_codes_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stats about HS codes in database."""
    result = await db.execute(
        select(func.count()).select_from(Classifier).where(
            Classifier.classifier_type == "hs_code"
        )
    )
    total = result.scalar() or 0

    result_groups = await db.execute(
        select(func.count()).select_from(Classifier).where(
            Classifier.classifier_type == "hs_code",
            func.length(Classifier.code) == 2,
        )
    )
    groups = result_groups.scalar() or 0

    result_positions = await db.execute(
        select(func.count()).select_from(Classifier).where(
            Classifier.classifier_type == "hs_code",
            func.length(Classifier.code) == 4,
        )
    )
    positions = result_positions.scalar() or 0

    return {
        "total": total,
        "groups_2digit": groups,
        "positions_4digit": positions,
        "sub_positions": total - groups - positions,
        "source": "classifikators.ru / local seed",
    }
