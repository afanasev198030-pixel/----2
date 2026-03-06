import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Declaration, DeclarationItem, DeclarationStatus, User
from app.schemas import (
    DeclarationItemCreate,
    DeclarationItemUpdate,
    DeclarationItemResponse,
)

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/declarations/{declaration_id}/items",
    tags=["declaration-items"],
)


async def get_declaration_or_404(
    declaration_id: uuid.UUID,
    db: AsyncSession,
    current_user: User,
) -> Declaration:
    """Helper to get declaration or raise 404."""
    result = await db.execute(
        select(Declaration).where(Declaration.id == declaration_id)
    )
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )
    
    # Check company access
    if current_user.company_id and declaration.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be associated with a company",
        )
    
    return declaration


@router.get("/", response_model=list[DeclarationItemResponse])
async def list_items(
    declaration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List items for a declaration."""
    declaration = await get_declaration_or_404(declaration_id, db, current_user)
    
    result = await db.execute(
        select(DeclarationItem)
        .where(DeclarationItem.declaration_id == declaration_id)
        .order_by(DeclarationItem.item_no)
    )
    items = result.scalars().all()
    
    return [DeclarationItemResponse.model_validate(item) for item in items]


@router.post("/", response_model=DeclarationItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    declaration_id: uuid.UUID,
    data: DeclarationItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an item to a declaration. Auto-set item_no to max+1 if not provided."""
    declaration = await get_declaration_or_404(declaration_id, db, current_user)
    
    # Check if declaration can be modified
    if declaration.status not in (DeclarationStatus.DRAFT, DeclarationStatus.CHECKING_LVL1):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot add items to declaration with status: {declaration.status}",
        )
    
    # Auto-set item_no if not provided
    item_no = data.item_no
    if item_no is None:
        result = await db.execute(
            select(func.max(DeclarationItem.item_no))
            .where(DeclarationItem.declaration_id == declaration_id)
        )
        max_item_no = result.scalar() or 0
        item_no = max_item_no + 1
    
    # Create item
    item = DeclarationItem(
        declaration_id=declaration_id,
        item_no=item_no,
        description=data.description,
        package_count=data.package_count,
        package_type=data.package_type,
        commercial_name=data.commercial_name,
        hs_code=data.hs_code,
        hs_code_letters=data.hs_code_letters,
        hs_code_extra=data.hs_code_extra,
        country_origin_code=data.country_origin_code,
        country_origin_pref_code=data.country_origin_pref_code,
        gross_weight=data.gross_weight,
        preference_code=data.preference_code,
        procedure_code=data.procedure_code,
        net_weight=data.net_weight,
        quota_info=data.quota_info,
        prev_doc_ref=data.prev_doc_ref,
        additional_unit=data.additional_unit,
        additional_unit_qty=data.additional_unit_qty,
        unit_price=data.unit_price,
        mos_method_code=data.mos_method_code,
        customs_value_rub=data.customs_value_rub,
        statistical_value_usd=data.statistical_value_usd,
        documents_json=data.documents_json,
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    logger.info(
        "declaration_item_created",
        declaration_id=str(declaration_id),
        item_id=str(item.id),
        item_no=item_no,
        user_id=str(current_user.id),
    )
    
    return DeclarationItemResponse.model_validate(item)


@router.get("/{item_id}", response_model=DeclarationItemResponse)
async def get_item(
    declaration_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single item."""
    declaration = await get_declaration_or_404(declaration_id, db, current_user)
    
    result = await db.execute(
        select(DeclarationItem).where(
            DeclarationItem.id == item_id,
            DeclarationItem.declaration_id == declaration_id,
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    
    return DeclarationItemResponse.model_validate(item)


@router.put("/{item_id}", response_model=DeclarationItemResponse)
async def update_item(
    declaration_id: uuid.UUID,
    item_id: uuid.UUID,
    data: DeclarationItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update item fields."""
    declaration = await get_declaration_or_404(declaration_id, db, current_user)
    
    # Check if declaration can be modified
    if declaration.status not in (DeclarationStatus.DRAFT, DeclarationStatus.CHECKING_LVL1):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update items in declaration with status: {declaration.status}",
        )
    
    result = await db.execute(
        select(DeclarationItem).where(
            DeclarationItem.id == item_id,
            DeclarationItem.declaration_id == declaration_id,
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    item.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(item)
    
    logger.info(
        "declaration_item_updated",
        declaration_id=str(declaration_id),
        item_id=str(item_id),
        user_id=str(current_user.id),
    )

    # Self-learning: при обновлении hs_code — сохранить как прецедент
    if "hs_code" in update_data and item.description and item.hs_code:
        try:
            import httpx as _httpx
            import os
            from app.middleware.logging_middleware import tracing_headers
            ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
            _httpx.post(f"{ai_url}/api/v1/ai/feedback", json={
                "declaration_id": str(declaration_id),
                "item_id": str(item_id),
                "feedback_type": "hs_confirmed",
                "predicted_value": "",
                "actual_value": item.hs_code,
                "description": item.description[:300],
            }, headers=tracing_headers(), timeout=5)
            logger.info("hs_feedback_sent", description=item.description[:50], hs_code=item.hs_code)
        except Exception as e:
            logger.debug("hs_feedback_failed", error=str(e)[:100])
    
    return DeclarationItemResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    declaration_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an item."""
    declaration = await get_declaration_or_404(declaration_id, db, current_user)
    
    # Check if declaration can be modified
    if declaration.status not in (DeclarationStatus.DRAFT, DeclarationStatus.CHECKING_LVL1):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete items from declaration with status: {declaration.status}",
        )
    
    result = await db.execute(
        select(DeclarationItem).where(
            DeclarationItem.id == item_id,
            DeclarationItem.declaration_id == declaration_id,
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    
    await db.delete(item)
    await db.commit()
    
    logger.info(
        "declaration_item_deleted",
        declaration_id=str(declaration_id),
        item_id=str(item_id),
        user_id=str(current_user.id),
    )
