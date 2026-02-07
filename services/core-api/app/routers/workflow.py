import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration,
    DeclarationStatus,
    DeclarationLog,
    DeclarationStatusHistory,
    User,
)
from app.schemas import StatusChangeRequest

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/declarations/{declaration_id}/status",
    tags=["workflow"],
)

# Define valid status transitions
VALID_TRANSITIONS = {
    DeclarationStatus.DRAFT: {DeclarationStatus.CHECKING_LVL1},
    DeclarationStatus.CHECKING_LVL1: {DeclarationStatus.CHECKING_LVL2, DeclarationStatus.DRAFT},
    DeclarationStatus.CHECKING_LVL2: {DeclarationStatus.FINAL_CHECK, DeclarationStatus.DRAFT},
    DeclarationStatus.FINAL_CHECK: {DeclarationStatus.SIGNED, DeclarationStatus.DRAFT},
    DeclarationStatus.SIGNED: {DeclarationStatus.SENT},
}


@router.post("/", response_model=dict)
async def change_status(
    declaration_id: uuid.UUID,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change declaration status. Validates transitions."""
    # Get declaration
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
    
    # Parse new status
    try:
        new_status = DeclarationStatus(data.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {data.new_status}",
        )
    
    current_status = DeclarationStatus(declaration.status)
    
    # Check if transition is valid
    allowed_transitions = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition: {current_status.value} -> {new_status.value}. "
                f"Allowed transitions: {[s.value for s in allowed_transitions]}"
            ),
        )
    
    # Store old status
    old_status = declaration.status
    
    # Update status
    declaration.status = new_status
    declaration.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(declaration)
    
    # Create declaration_log entry
    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=current_user.id,
        action="status_change",
        old_value={"status": old_status},
        new_value={"status": new_status.value},
    )
    db.add(log_entry)
    
    # Create declaration_status_history entry
    history_entry = DeclarationStatusHistory(
        declaration_id=declaration.id,
        status_code=new_status.value,
        status_text=f"Status changed from {old_status} to {new_status.value}",
        source="system",
    )
    db.add(history_entry)
    
    await db.commit()
    
    logger.info(
        "declaration_status_changed",
        declaration_id=str(declaration.id),
        old_status=old_status,
        new_status=new_status.value,
        user_id=str(current_user.id),
    )
    
    return {
        "declaration_id": str(declaration.id),
        "old_status": old_status,
        "new_status": new_status.value,
        "changed_at": datetime.utcnow().isoformat(),
    }
