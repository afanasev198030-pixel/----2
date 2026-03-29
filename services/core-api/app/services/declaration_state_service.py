"""
Domain service for declaration state management.

Centralises all status/signature/processing transitions so that routers
only call thin wrappers instead of implementing business rules inline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Declaration,
    DeclarationStatus,
    ProcessingStatus,
    SignatureStatus,
    DeclarationLog,
    DeclarationStatusHistory,
)

logger = structlog.get_logger()

STATUS_DISPLAY = {
    DeclarationStatus.NEW: "Новая",
    DeclarationStatus.REQUIRES_ATTENTION: "Требует внимания",
    DeclarationStatus.READY_TO_SEND: "Готово к отправке",
    DeclarationStatus.SENT: "Отправлено",
}

PROCESSING_DISPLAY = {
    ProcessingStatus.NOT_STARTED: "Распознавание не запускалось",
    ProcessingStatus.PROCESSING: "В обработке",
    ProcessingStatus.AUTO_FILLED: "Заполнена автоматически",
    ProcessingStatus.PROCESSING_ERROR: "Ошибка обработки",
}

SIGNATURE_DISPLAY = {
    SignatureStatus.UNSIGNED: "Не подписана",
    SignatureStatus.SIGNED: "Подписана",
}


async def recalculate_declaration_state(
    declaration: Declaration,
    db: AsyncSession,
    *,
    user_id: str | None = None,
    run_checks_fn=None,
) -> Declaration:
    """Re-evaluate the declaration and set status to REQUIRES_ATTENTION or
    READY_TO_SEND based on current validation results.

    Does nothing if status is SENT (post-send states are immutable).

    ``run_checks_fn`` is injected by the caller (typically
    ``run_pre_send_checks`` from workflow) to avoid a circular import.
    """
    if declaration.status == DeclarationStatus.SENT.value:
        return declaration

    if run_checks_fn is None:
        from app.routers.workflow import run_pre_send_checks
        run_checks_fn = run_pre_send_checks

    check_result = await run_checks_fn(declaration, db)

    old_status = declaration.status
    if check_result.blocking_count > 0:
        new_status = DeclarationStatus.REQUIRES_ATTENTION
    else:
        new_status = DeclarationStatus.READY_TO_SEND

    if old_status == new_status.value:
        return declaration

    declaration.status = new_status.value
    declaration.updated_at = datetime.utcnow()

    _add_status_log(declaration, old_status, new_status.value, user_id, db)

    logger.info(
        "declaration_state_recalculated",
        declaration_id=str(declaration.id),
        old_status=old_status,
        new_status=new_status.value,
        blocking_count=check_result.blocking_count,
    )

    return declaration


def reset_signature_if_needed(
    declaration: Declaration,
    db: AsyncSession,
    *,
    user_id: str | None = None,
) -> bool:
    """Drop signature back to UNSIGNED when it was SIGNED.

    Returns True if signature was actually reset.
    """
    if declaration.signature_status != SignatureStatus.SIGNED.value:
        return False

    declaration.signature_status = SignatureStatus.UNSIGNED.value
    declaration.updated_at = datetime.utcnow()

    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=user_id,
        action="signature_reset",
        old_value={"signature_status": SignatureStatus.SIGNED.value},
        new_value={"signature_status": SignatureStatus.UNSIGNED.value},
    )
    db.add(log_entry)

    logger.info(
        "declaration_signature_reset",
        declaration_id=str(declaration.id),
    )
    return True


def can_send(declaration: Declaration) -> bool:
    """Guard: declaration may only be sent when READY_TO_SEND + SIGNED."""
    return (
        declaration.status == DeclarationStatus.READY_TO_SEND.value
        and declaration.signature_status == SignatureStatus.SIGNED.value
    )


async def handle_first_open(
    declaration: Declaration,
    db: AsyncSession,
    *,
    user_id: str | None = None,
) -> Declaration:
    """Transition from NEW on first user open.

    Runs validation and moves to REQUIRES_ATTENTION or READY_TO_SEND.
    """
    if declaration.status != DeclarationStatus.NEW.value:
        return declaration

    return await recalculate_declaration_state(
        declaration, db, user_id=user_id,
    )


def set_processing_status(
    declaration: Declaration,
    new_status: ProcessingStatus,
    db: AsyncSession,
    *,
    user_id: str | None = None,
) -> None:
    """Transition processing_status with logging."""
    old = declaration.processing_status
    declaration.processing_status = new_status.value
    declaration.updated_at = datetime.utcnow()

    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=user_id,
        action="processing_status_change",
        old_value={"processing_status": old},
        new_value={"processing_status": new_status.value},
    )
    db.add(log_entry)


def _add_status_log(
    declaration: Declaration,
    old_status: str,
    new_status: str,
    user_id: str | None,
    db: AsyncSession,
) -> None:
    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=user_id,
        action="status_change",
        old_value={"status": old_status},
        new_value={"status": new_status},
    )
    db.add(log_entry)

    history_entry = DeclarationStatusHistory(
        declaration_id=declaration.id,
        status_code=new_status,
        status_text=f"{STATUS_DISPLAY.get(DeclarationStatus(old_status), old_status)} → "
                    f"{STATUS_DISPLAY.get(DeclarationStatus(new_status), new_status)}",
        source="system",
    )
    db.add(history_entry)
