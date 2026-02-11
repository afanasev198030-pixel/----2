"""Сервис аудит-лога: запись всех действий пользователей."""
import uuid
from typing import Optional
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.audit_log import AuditLog

logger = structlog.get_logger()


async def log_action(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
):
    """Записать действие в аудит-лог.

    Actions: login, register, create_declaration, update_declaration,
    delete_declaration, view_declaration, upload_document, apply_parsed,
    create_item, update_item, delete_item, update_profile, admin_update_user, ...
    """
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent", "")[:500]

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(entry)
    # Don't commit — caller will commit with their transaction

    logger.info(
        "audit_log",
        user_id=str(user_id) if user_id else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
