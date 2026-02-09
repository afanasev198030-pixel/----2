"""CRUD компаний."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models import Company, User
from app.models.user import UserRole
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Company))
    return [CompanyResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    company = Company(name=data.name, inn=data.inn, kpp=data.kpp, ogrn=data.ogrn, address=data.address, country_code=data.country_code)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    logger.info("company_created", id=str(company.id), name=company.name)
    return CompanyResponse.model_validate(company)


@router.get("/{id}", response_model=CompanyResponse)
async def get_company(id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Company).where(Company.id == id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.put("/{id}", response_model=CompanyResponse)
async def update_company(id: uuid.UUID, data: CompanyUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role(UserRole.ADMIN))):
    result = await db.execute(select(Company).where(Company.id == id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)
