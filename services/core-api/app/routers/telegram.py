import uuid
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
