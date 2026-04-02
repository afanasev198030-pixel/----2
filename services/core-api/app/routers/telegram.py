import uuid
import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
import structlog
import redis.asyncio as redis

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.models.declaration import Declaration, DeclarationStatus, ProcessingStatus
from app.models.document import Document, DocumentType
from app.models.declaration_log import DeclarationLog
from app.schemas import TelegramLinkRequest, TelegramLinkResponse, TelegramLogRequest
from app.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])

async def get_redis():
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.post("/generate-link-token")
async def generate_link_token(
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Generate a one-time token to link Telegram account."""
    token = secrets.token_urlsafe(16)
    # Store token with 10 minutes expiration
    await redis_client.setex(f"tg_link:{token}", 600, str(current_user.id))
    
    logger.info("telegram_link_token_generated", user_id=str(current_user.id))
    
    # Get bot username from DB settings or env
    from app.routers.settings import _get_setting
    import os
    bot_username = (await _get_setting(db, "telegram_bot_username") or os.environ.get("TELEGRAM_BOT_USERNAME", "YourBrokerBot")).lstrip("@")
    
    return {"link_url": f"https://t.me/{bot_username}?start={token}", "token": token}

@router.post("/link", response_model=TelegramLinkResponse)
async def link_telegram_account(
    data: TelegramLinkRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """Link a Telegram account using the one-time token (called by bot-service)."""
    user_id_str = await redis_client.get(f"tg_link:{data.token}")
    
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )
        
    user_id = uuid.UUID(user_id_str)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    # Check if telegram_id is already used by someone else
    check_result = await db.execute(select(User).where(User.telegram_id == data.telegram_id))
    existing_user = check_result.scalar_one_or_none()
    
    if existing_user and existing_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram account already linked to another user",
        )
        
    user.telegram_id = data.telegram_id
    await db.commit()
    
    # Delete the used token
    await redis_client.delete(f"tg_link:{data.token}")
    
    logger.info("telegram_account_linked", user_id=str(user.id), telegram_id=data.telegram_id)
    
    return TelegramLinkResponse(
        status="success",
        message="Telegram account successfully linked",
        user_id=str(user.id)
    )

@router.get("/user/{telegram_id}", response_model=dict)
async def get_user_by_telegram_id(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get user info by telegram_id (called by bot-service)."""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
        
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "company_id": str(user.company_id) if user.company_id else None,
        "is_active": user.is_active
    }

@router.post("/log")
async def log_telegram_action(
    data: TelegramLogRequest,
    db: AsyncSession = Depends(get_db),
):
    """Log action from telegram bot."""
    from app.services.audit import log_action
    
    await log_action(
        db, 
        uuid.UUID(data.user_id), 
        data.action, 
        resource_type="telegram", 
        details=data.details
    )
    await db.commit()
    return {"status": "ok"}


class BotCreateDeclarationRequest(BaseModel):
    user_id: str
    company_id: str


class BotAttachDocumentRequest(BaseModel):
    user_id: str
    declaration_id: str
    file_key: str
    original_filename: str


@router.post("/create-declaration")
async def bot_create_declaration(
    data: BotCreateDeclarationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a draft declaration from bot-service (no JWT, internal network only)."""
    user_id = uuid.UUID(data.user_id)
    company_id = uuid.UUID(data.company_id)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    declaration = Declaration(
        company_id=company_id,
        status=DeclarationStatus.NEW,
        processing_status=ProcessingStatus.NOT_STARTED.value,
        signature_status="unsigned",
        created_by=user_id,
    )
    db.add(declaration)
    await db.commit()
    await db.refresh(declaration)

    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=user_id,
        action="create",
        new_value={"status": "new", "source": "telegram"},
    )
    db.add(log_entry)
    await db.commit()

    logger.info("declaration_created_via_telegram", declaration_id=str(declaration.id), user_id=data.user_id)
    return {"id": str(declaration.id)}


@router.post("/attach-document")
async def bot_attach_document(
    data: BotAttachDocumentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Attach a document to a declaration from bot-service (no JWT, internal network only)."""
    document = Document(
        declaration_id=uuid.UUID(data.declaration_id),
        doc_type=DocumentType.OTHER,
        file_key=data.file_key,
        original_filename=data.original_filename,
        mime_type="application/octet-stream",
        file_size=0,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info(
        "document_attached_via_telegram",
        document_id=str(document.id),
        declaration_id=data.declaration_id,
        filename=data.original_filename,
    )
    return {"id": str(document.id)}


class BotApplyParsedRequest(BaseModel):
    user_id: str
    declaration_id: str
    parsed_data: dict


@router.post("/apply-parsed")
async def bot_apply_parsed(
    data: BotApplyParsedRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply parse-smart results to a declaration (no JWT, internal network only)."""
    from app.routers.apply_parsed import apply_parsed_data, ApplyParsedRequest

    user_id = uuid.UUID(data.user_id)
    declaration_id = uuid.UUID(data.declaration_id)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        parsed_request = ApplyParsedRequest(**data.parsed_data)
    except Exception as e:
        logger.error("apply_parsed_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid parsed data: {str(e)}")

    logger.info("apply_parsed_via_telegram", declaration_id=str(declaration_id), user_id=data.user_id)
    return await apply_parsed_data(declaration_id, parsed_request, db, user)


# ==================== INTERNAL API FOR AGENT TOOLS ====================

async def _resolve_user_by_telegram(telegram_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _resolve_user(identifier: str, db: AsyncSession) -> User:
    """Resolve user by UUID user_id or telegram_id."""
    try:
        uid = uuid.UUID(identifier)
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if user:
            return user
    except (ValueError, AttributeError):
        pass
    return await _resolve_user_by_telegram(identifier, db)


@router.get("/user/{telegram_id}/declarations")
async def get_user_declarations_by_telegram(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, le=50),
):
    """List user declarations by telegram_id or user_id UUID (internal, no JWT)."""
    user = await _resolve_user(telegram_id, db)

    from app.models.declaration_item import DeclarationItem

    stmt = (
        select(Declaration)
        .where(Declaration.created_by == user.id)
        .order_by(desc(Declaration.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    declarations = result.scalars().all()

    items = []
    for d in declarations:
        item_count_q = await db.execute(
            select(func.count()).select_from(DeclarationItem).where(DeclarationItem.declaration_id == d.id)
        )
        items.append({
            "id": str(d.id),
            "number_internal": d.number_internal,
            "status": d.status,
            "processing_status": d.processing_status,
            "signature_status": d.signature_status,
            "items_count": item_count_q.scalar() or 0,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        })

    return {"declarations": items, "total": len(items), "user_id": str(user.id)}


@router.get("/user/{telegram_id}/declaration/{declaration_id}/status")
async def get_declaration_status_by_telegram(
    telegram_id: str,
    declaration_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Detailed status of a declaration including pre-send checks (internal, no JWT)."""
    user = await _resolve_user(telegram_id, db)

    decl_uuid = uuid.UUID(declaration_id)
    result = await db.execute(
        select(Declaration).where(
            Declaration.id == decl_uuid,
            Declaration.created_by == user.id,
        )
    )
    declaration = result.scalar_one_or_none()
    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration not found")

    from app.routers.workflow import run_pre_send_checks
    check_result = await run_pre_send_checks(declaration, db)

    from app.models.declaration_item import DeclarationItem
    item_count_q = await db.execute(
        select(func.count()).select_from(DeclarationItem).where(DeclarationItem.declaration_id == decl_uuid)
    )
    doc_count_q = await db.execute(
        select(func.count()).select_from(Document).where(Document.declaration_id == decl_uuid)
    )

    return {
        "id": str(declaration.id),
        "number_internal": declaration.number_internal,
        "status": declaration.status,
        "processing_status": declaration.processing_status,
        "signature_status": declaration.signature_status,
        "items_count": item_count_q.scalar() or 0,
        "documents_count": doc_count_q.scalar() or 0,
        "pre_send_checks": {
            "blocking_count": check_result.blocking_count,
            "warning_count": check_result.warning_count,
            "checks": [
                {"label": c.label, "severity": c.severity, "passed": c.passed}
                for c in check_result.checks
            ],
        },
        "created_at": declaration.created_at.isoformat() if declaration.created_at else None,
        "updated_at": declaration.updated_at.isoformat() if declaration.updated_at else None,
    }


@router.get("/user/{telegram_id}/profile")
async def get_user_profile_by_telegram(
    telegram_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Full user profile by telegram_id or user_id UUID (internal, no JWT)."""
    user = await _resolve_user(telegram_id, db)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "company_id": str(user.company_id) if user.company_id else None,
        "telegram_id": user.telegram_id,
        "is_active": user.is_active,
    }


class BotSignRequest(BaseModel):
    user_id: str
    declaration_id: str


@router.post("/sign-declaration")
async def bot_sign_declaration(
    data: BotSignRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sign a declaration from bot (internal, no JWT)."""
    from app.models.declaration import SignatureStatus
    from app.services.declaration_state_service import can_send

    user_id = uuid.UUID(data.user_id)
    decl_id = uuid.UUID(data.declaration_id)

    result = await db.execute(
        select(Declaration).where(Declaration.id == decl_id, Declaration.created_by == user_id)
    )
    declaration = result.scalar_one_or_none()
    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration not found")

    if declaration.status != DeclarationStatus.READY_TO_SEND.value:
        raise HTTPException(
            status_code=409,
            detail=f"Подпись возможна только в статусе «Готово к отправке». Текущий: {declaration.status}",
        )

    if declaration.signature_status == SignatureStatus.SIGNED.value:
        return {"status": "already_signed"}

    from datetime import datetime
    declaration.signature_status = SignatureStatus.SIGNED.value
    declaration.updated_at = datetime.utcnow()

    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=user_id,
        action="signature_change",
        old_value={"signature_status": SignatureStatus.UNSIGNED.value},
        new_value={"signature_status": SignatureStatus.SIGNED.value, "source": "telegram"},
    )
    db.add(log_entry)
    await db.commit()

    logger.info("declaration_signed_via_telegram", declaration_id=data.declaration_id)
    return {"status": "signed"}
