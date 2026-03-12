import uuid
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import redis.asyncio as redis

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
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
    bot_username = await _get_setting(db, "telegram_bot_username") or os.environ.get("TELEGRAM_BOT_USERNAME", "YourBrokerBot")
    
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
