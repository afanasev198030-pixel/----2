import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.broker_client import BrokerClient
from app.models.declaration import Declaration
from app.schemas.broker_client import (
    BrokerClientCreate,
    BrokerClientUpdate,
    BrokerClientResponse,
)
from app.schemas.declaration import DeclarationListResponse
from app.schemas.common import PaginatedResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/broker", tags=["broker"])


@router.get("/clients", response_model=list[BrokerClientResponse])
async def list_broker_clients(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """List all clients of the current broker company."""
    query = (
        select(BrokerClient)
        .options(selectinload(BrokerClient.client_company))
    )

    # Brokers see only their own clients; admins see all
    if current_user.role != UserRole.ADMIN.value:
        query = query.where(
            BrokerClient.broker_company_id == current_user.company_id
        )

    if is_active is not None:
        query = query.where(BrokerClient.is_active == is_active)

    query = query.order_by(BrokerClient.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    logger.info(
        "broker_clients_listed",
        user_id=str(current_user.id),
        count=len(items),
    )
    return items


@router.post(
    "/clients",
    response_model=BrokerClientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_client(
    body: BrokerClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """Create a new broker-client relationship.
    Either reference an existing company by client_company_id
    or create a new company inline via new_company.
    """
    broker_company_id = current_user.company_id
    if not broker_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user has no company assigned",
        )

    # Determine client company id
    client_company_id = body.client_company_id

    if client_company_id is None and body.new_company is not None:
        # Create new company
        new_company = Company(
            name=body.new_company.name,
            inn=body.new_company.inn,
            kpp=body.new_company.kpp,
            ogrn=body.new_company.ogrn,
            address=body.new_company.address,
            country_code=body.new_company.country_code,
            company_type=body.new_company.company_type or "client",
            contact_email=body.new_company.contact_email,
            contact_phone=body.new_company.contact_phone,
        )
        db.add(new_company)
        await db.flush()
        client_company_id = new_company.id
        logger.info(
            "broker_client_company_created",
            company_id=str(client_company_id),
            inn=body.new_company.inn,
        )
    elif client_company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either client_company_id or new_company must be provided",
        )

    # Check if relationship already exists
    existing = await db.execute(
        select(BrokerClient).where(
            BrokerClient.broker_company_id == broker_company_id,
            BrokerClient.client_company_id == client_company_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Broker-client relationship already exists",
        )

    broker_client = BrokerClient(
        broker_company_id=broker_company_id,
        client_company_id=client_company_id,
        contract_number=body.contract_number,
        contract_date=body.contract_date,
        tariff_plan=body.tariff_plan,
    )
    db.add(broker_client)
    await db.commit()
    await db.refresh(broker_client, attribute_names=["client_company"])

    logger.info(
        "broker_client_created",
        broker_client_id=str(broker_client.id),
        broker_company_id=str(broker_company_id),
        client_company_id=str(client_company_id),
    )
    return broker_client


@router.get("/clients/{client_id}", response_model=BrokerClientResponse)
async def get_broker_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """Get a specific broker-client relationship."""
    query = (
        select(BrokerClient)
        .options(selectinload(BrokerClient.client_company))
        .where(BrokerClient.id == client_id)
    )

    if current_user.role != UserRole.ADMIN.value:
        query = query.where(
            BrokerClient.broker_company_id == current_user.company_id
        )

    result = await db.execute(query)
    broker_client = result.scalar_one_or_none()

    if not broker_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker-client relationship not found",
        )
    return broker_client


@router.put("/clients/{client_id}", response_model=BrokerClientResponse)
async def update_broker_client(
    client_id: uuid.UUID,
    body: BrokerClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """Update contract details or tariff of a broker-client relationship."""
    query = select(BrokerClient).where(BrokerClient.id == client_id)

    if current_user.role != UserRole.ADMIN.value:
        query = query.where(
            BrokerClient.broker_company_id == current_user.company_id
        )

    result = await db.execute(query)
    broker_client = result.scalar_one_or_none()

    if not broker_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker-client relationship not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(broker_client, field, value)

    await db.commit()
    await db.refresh(broker_client, attribute_names=["client_company"])

    logger.info(
        "broker_client_updated",
        broker_client_id=str(client_id),
        updated_fields=list(update_data.keys()),
    )
    return broker_client


@router.delete("/clients/{client_id}", response_model=BrokerClientResponse)
async def delete_broker_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """Soft-delete a broker-client relationship (set is_active=false)."""
    query = select(BrokerClient).where(BrokerClient.id == client_id)

    if current_user.role != UserRole.ADMIN.value:
        query = query.where(
            BrokerClient.broker_company_id == current_user.company_id
        )

    result = await db.execute(query)
    broker_client = result.scalar_one_or_none()

    if not broker_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker-client relationship not found",
        )

    broker_client.is_active = False
    await db.commit()
    await db.refresh(broker_client, attribute_names=["client_company"])

    logger.info(
        "broker_client_deactivated",
        broker_client_id=str(client_id),
    )
    return broker_client


@router.get(
    "/clients/{client_id}/declarations",
    response_model=PaginatedResponse,
)
async def list_client_declarations(
    client_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.BROKER, UserRole.ADMIN)),
):
    """List declarations for a specific broker client, filtered by client company_id."""
    # Verify broker-client relationship
    bc_query = select(BrokerClient).where(BrokerClient.id == client_id)

    if current_user.role != UserRole.ADMIN.value:
        bc_query = bc_query.where(
            BrokerClient.broker_company_id == current_user.company_id
        )

    result = await db.execute(bc_query)
    broker_client = result.scalar_one_or_none()

    if not broker_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker-client relationship not found",
        )

    # Fetch declarations for this client company
    count_query = (
        select(func.count())
        .select_from(Declaration)
        .where(Declaration.company_id == broker_client.client_company_id)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    pages = (total + per_page - 1) // per_page if total > 0 else 0
    offset = (page - 1) * per_page

    decl_query = (
        select(Declaration)
        .where(Declaration.company_id == broker_client.client_company_id)
        .order_by(Declaration.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    decl_result = await db.execute(decl_query)
    declarations = decl_result.scalars().all()

    logger.info(
        "broker_client_declarations_listed",
        broker_client_id=str(client_id),
        client_company_id=str(broker_client.client_company_id),
        count=len(declarations),
    )

    return PaginatedResponse(
        items=[DeclarationListResponse.model_validate(d) for d in declarations],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )
