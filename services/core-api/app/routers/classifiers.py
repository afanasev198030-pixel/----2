from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Classifier, User, HsRequirement, ClassifierSyncLog
from app.schemas import ClassifierResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/classifiers", tags=["classifiers"])


@router.get("", response_model=list[ClassifierResponse])
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


@router.get("/hs-duty-rate")
async def get_hs_duty_rate(
    code: str = Query(..., min_length=2, max_length=10),
    db: AsyncSession = Depends(get_db),
):
    """Return duty_rate from classifier meta for a given HS code (internal, no auth).

    Tries exact code first, then falls back to shorter prefixes (8, 6, 4 digits).
    """
    prefixes = [code]
    if len(code) > 4:
        for length in (8, 6, 4):
            if len(code) > length:
                prefixes.append(code[:length])

    for prefix in prefixes:
        result = await db.execute(
            select(Classifier).where(
                Classifier.classifier_type == "hs_code",
                Classifier.code == prefix,
                Classifier.is_active == True,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        if row and row.meta and row.meta.get("duty_rate") is not None:
            return {
                "code": row.code,
                "duty_rate": row.meta["duty_rate"],
                "duty_type": row.meta.get("duty_type", "ad_valorem"),
            }

    return {"code": code, "duty_rate": None, "duty_type": None}


@router.get("/subcodes")
async def list_subcodes(
    prefix: str = Query(..., min_length=4, max_length=8),
    classifier_type: str = Query("hs_code"),
    db: AsyncSession = Depends(get_db),
):
    """Подкоды по префиксу (internal, без auth) — для двухэтапной классификации ТН ВЭД."""
    query = select(Classifier).where(
        Classifier.classifier_type == classifier_type,
        Classifier.code.like(f"{prefix}%"),
        Classifier.is_active == True,
        func.length(Classifier.code) == 10,
    ).order_by(Classifier.code).limit(30)
    result = await db.execute(query)
    codes = result.scalars().all()
    return [{"code": c.code, "name_ru": c.name_ru or ""} for c in codes]


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


@router.get("/hs-requirements")
async def get_hs_requirements(
    hs_code: str = Query(..., description="Full or partial HS code to check requirements for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get certificate/license/permit requirements for an HS code.

    Generates all possible prefixes of the given HS code and returns
    matching requirements sorted from most specific to least specific.
    """
    # Generate all prefixes: 8517711900 → ['8517711900','851771190',...,'85','8']
    hs_code_clean = hs_code.strip().replace(".", "").replace(" ", "")
    if len(hs_code_clean) < 2:
        return []

    prefixes = [hs_code_clean[:i] for i in range(len(hs_code_clean), 0, -1)]

    query = (
        select(HsRequirement)
        .where(
            HsRequirement.hs_code_prefix.in_(prefixes),
            HsRequirement.is_active == True,
        )
        .order_by(func.length(HsRequirement.hs_code_prefix).desc())
    )

    result = await db.execute(query)
    requirements = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "hs_code_prefix": r.hs_code_prefix,
            "requirement_type": r.requirement_type,
            "document_name": r.document_name,
            "issuing_authority": r.issuing_authority,
            "legal_basis": r.legal_basis,
            "description": r.description,
        }
        for r in requirements
    ]


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


@router.get("/sync-info")
async def get_classifier_sync_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get last sync timestamp and record count per classifier type."""
    from app.services.eec_classifier_config import EEC_CLASSIFIERS

    subq = (
        select(
            ClassifierSyncLog.classifier_type,
            func.max(ClassifierSyncLog.last_sync_at).label("max_sync"),
        )
        .where(ClassifierSyncLog.status == "success")
        .group_by(ClassifierSyncLog.classifier_type)
        .subquery()
    )
    query = select(ClassifierSyncLog).join(
        subq,
        and_(
            ClassifierSyncLog.classifier_type == subq.c.classifier_type,
            ClassifierSyncLog.last_sync_at == subq.c.max_sync,
        ),
    )
    result = await db.execute(query)
    logs = {log.classifier_type: log for log in result.scalars().all()}

    counts_result = await db.execute(
        select(
            Classifier.classifier_type,
            func.count().label("cnt"),
        )
        .where(Classifier.is_active == True)
        .group_by(Classifier.classifier_type)
    )
    counts = {row[0]: row[1] for row in counts_result.all()}

    items = []
    for ct, cfg in EEC_CLASSIFIERS.items():
        log = logs.get(ct)
        items.append({
            "classifier_type": ct,
            "title": cfg["title"],
            "active_records": counts.get(ct, 0),
            "last_sync_at": log.last_sync_at.isoformat() if log else None,
            "source": "eec_portal" if log else ("seed" if counts.get(ct, 0) > 0 else "none"),
        })

    return {"items": items}
