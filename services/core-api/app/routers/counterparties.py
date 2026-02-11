"""CRUD контрагентов."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Counterparty, User
from app.schemas.counterparty import CounterpartyCreate, CounterpartyUpdate, CounterpartyResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/counterparties", tags=["counterparties"])


@router.get("/", response_model=list[CounterpartyResponse])
async def list_counterparties(
    q: Optional[str] = None,
    type: Optional[str] = None,
    per_page: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Counterparty)
    if current_user.company_id:
        query = query.where(Counterparty.company_id == current_user.company_id)
    if type:
        query = query.where(Counterparty.type == type)
    if q:
        query = query.where(or_(
            Counterparty.name.ilike(f"%{q}%"),
            Counterparty.tax_number.ilike(f"%{q}%"),
        ))
    query = query.limit(per_page)
    result = await db.execute(query)
    return [CounterpartyResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/", response_model=CounterpartyResponse, status_code=201)
async def create_counterparty(
    data: CounterpartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cp = Counterparty(
        type=data.type,
        name=data.name,
        country_code=data.country_code,
        registration_number=data.registration_number,
        tax_number=data.tax_number,
        address=data.address,
        company_id=data.company_id or current_user.company_id,
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    logger.info("counterparty_created", id=str(cp.id), name=cp.name, type=cp.type)
    return CounterpartyResponse.model_validate(cp)


@router.get("/{id}", response_model=CounterpartyResponse)
async def get_counterparty(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Counterparty).options(selectinload(Counterparty.company)).where(Counterparty.id == id)
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return CounterpartyResponse.model_validate(cp)


@router.put("/{id}", response_model=CounterpartyResponse)
async def update_counterparty(
    id: uuid.UUID,
    data: CounterpartyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Counterparty).where(Counterparty.id == id))
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cp, field, value)
    await db.commit()
    await db.refresh(cp)
    return CounterpartyResponse.model_validate(cp)


@router.delete("/{id}", status_code=204)
async def delete_counterparty(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Counterparty).where(Counterparty.id == id))
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    await db.delete(cp)
    await db.commit()
