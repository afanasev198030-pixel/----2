import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import (
    Declaration,
    DeclarationStatus,
    DeclarationItem,
    DeclarationLog,
    DeclarationStatusHistory,
    Document,
    User,
)
from app.models.parse_issue import ParseIssue
from app.schemas import StatusChangeRequest

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/declarations/{declaration_id}",
    tags=["workflow"],
)

VALID_TRANSITIONS = {
    DeclarationStatus.DRAFT: {DeclarationStatus.CHECKING_LVL1},
    DeclarationStatus.CHECKING_LVL1: {DeclarationStatus.CHECKING_LVL2, DeclarationStatus.DRAFT},
    DeclarationStatus.CHECKING_LVL2: {DeclarationStatus.FINAL_CHECK, DeclarationStatus.DRAFT},
    DeclarationStatus.FINAL_CHECK: {DeclarationStatus.SIGNED, DeclarationStatus.DRAFT},
    DeclarationStatus.SIGNED: {DeclarationStatus.SENT},
}

REQUIRED_FIELDS_FOR_SEND = [
    "type_code", "company_id", "country_dispatch_code", "country_destination_code",
    "incoterms_code", "currency_code", "total_invoice_value",
]

GATED_STATUSES = {DeclarationStatus.SIGNED, DeclarationStatus.SENT}


class PreSendCheck(BaseModel):
    code: str
    severity: str
    field: Optional[str] = None
    blocking: bool
    message: str


class PreSendResult(BaseModel):
    passed: bool
    checks: list[PreSendCheck]
    blocking_count: int


async def run_pre_send_checks(
    declaration: Declaration, db: AsyncSession
) -> PreSendResult:
    """Server-side validation before allowing send/sign transitions."""
    checks: list[PreSendCheck] = []

    for field_name in REQUIRED_FIELDS_FOR_SEND:
        val = getattr(declaration, field_name, None)
        if val is None or (isinstance(val, str) and not val.strip()):
            checks.append(PreSendCheck(
                code="MISSING_REQUIRED_FIELD",
                severity="error",
                field=field_name,
                blocking=True,
                message=f"Обязательное поле «{field_name}» не заполнено",
            ))

    if not declaration.sender_counterparty_id:
        checks.append(PreSendCheck(
            code="MISSING_SENDER", severity="error", field="sender_counterparty_id",
            blocking=True, message="Не указан отправитель (графа 2)",
        ))
    if not declaration.receiver_counterparty_id:
        checks.append(PreSendCheck(
            code="MISSING_RECEIVER", severity="error", field="receiver_counterparty_id",
            blocking=True, message="Не указан получатель (графа 8)",
        ))

    items_result = await db.execute(
        select(func.count()).select_from(DeclarationItem).where(
            DeclarationItem.declaration_id == declaration.id
        )
    )
    items_count = items_result.scalar() or 0
    if items_count == 0:
        checks.append(PreSendCheck(
            code="NO_ITEMS", severity="error", field="items",
            blocking=True, message="Нет позиций товаров (графа 31/33)",
        ))

    docs_result = await db.execute(
        select(func.count()).select_from(Document).where(
            Document.declaration_id == declaration.id
        )
    )
    docs_count = docs_result.scalar() or 0
    if docs_count == 0:
        checks.append(PreSendCheck(
            code="NO_DOCUMENTS", severity="error", field="documents",
            blocking=True, message="Нет прикреплённых документов",
        ))

    items_no_hs = await db.execute(
        select(func.count()).select_from(DeclarationItem).where(
            DeclarationItem.declaration_id == declaration.id,
            (DeclarationItem.hs_code.is_(None)) | (DeclarationItem.hs_code == ""),
        )
    )
    no_hs_count = items_no_hs.scalar() or 0
    if no_hs_count > 0:
        checks.append(PreSendCheck(
            code="ITEMS_WITHOUT_HS", severity="error", field="hs_code",
            blocking=True, message=f"{no_hs_count} позиций без кода ТН ВЭД",
        ))

    blocking_issues = await db.execute(
        select(func.count()).select_from(ParseIssue).where(
            ParseIssue.declaration_id == declaration.id,
            ParseIssue.blocking.is_(True),
            ParseIssue.resolved.is_(False),
        )
    )
    blocking_count = blocking_issues.scalar() or 0
    if blocking_count > 0:
        checks.append(PreSendCheck(
            code="BLOCKING_ISSUES", severity="error", field="ai_issues",
            blocking=True, message=f"{blocking_count} нерешённых блокирующих проблем парсинга",
        ))

    if declaration.ai_issues:
        ai_blocking = [i for i in declaration.ai_issues if i.get("blocking") and not i.get("resolved")]
        if ai_blocking:
            checks.append(PreSendCheck(
                code="AI_BLOCKING_ISSUES", severity="error", field="ai_issues",
                blocking=True, message=f"{len(ai_blocking)} блокирующих AI-проблем",
            ))

    if declaration.total_gross_weight and declaration.total_net_weight:
        if declaration.total_net_weight > declaration.total_gross_weight:
            checks.append(PreSendCheck(
                code="WEIGHT_INCONSISTENCY", severity="warning", field="total_net_weight",
                blocking=False, message="Вес нетто превышает вес брутто",
            ))

    blocking_total = sum(1 for c in checks if c.blocking)
    return PreSendResult(
        passed=blocking_total == 0,
        checks=checks,
        blocking_count=blocking_total,
    )


@router.get("/pre-send-check")
async def pre_send_check_endpoint(
    declaration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run pre-send validation checks. Returns blocking/non-blocking issues."""
    result = await db.execute(
        select(Declaration).where(Declaration.id == declaration_id)
    )
    declaration = result.scalar_one_or_none()
    if not declaration:
        raise HTTPException(status_code=404, detail="Declaration not found")

    check_result = await run_pre_send_checks(declaration, db)
    return check_result


@router.post("/status/", response_model=dict)
async def change_status(
    declaration_id: uuid.UUID,
    data: StatusChangeRequest,
    force: bool = Query(False, description="Override blocking checks with audit reason"),
    override_reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change declaration status. Validates transitions. Runs pre-send gate for sign/send."""
    result = await db.execute(
        select(Declaration).where(Declaration.id == declaration_id)
    )
    declaration = result.scalar_one_or_none()

    if not declaration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Declaration not found",
        )

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

    try:
        new_status = DeclarationStatus(data.new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {data.new_status}",
        )

    current_status_enum = DeclarationStatus(declaration.status)

    allowed_transitions = VALID_TRANSITIONS.get(current_status_enum, set())
    if new_status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition: {current_status_enum.value} -> {new_status.value}. "
                f"Allowed transitions: {[s.value for s in allowed_transitions]}"
            ),
        )

    if new_status in GATED_STATUSES:
        gate_result = await run_pre_send_checks(declaration, db)
        if not gate_result.passed and not force:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f"Pre-send gate failed: {gate_result.blocking_count} blocking issues",
                    "checks": [c.model_dump() for c in gate_result.checks],
                    "blocking_count": gate_result.blocking_count,
                },
            )
        if not gate_result.passed and force:
            if not override_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="override_reason is required when force=true",
                )
            logger.warning(
                "pre_send_gate_overridden",
                declaration_id=str(declaration_id),
                user_id=str(current_user.id),
                reason=override_reason,
                blocking_count=gate_result.blocking_count,
            )

    old_status = declaration.status

    declaration.status = new_status
    declaration.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(declaration)

    log_entry = DeclarationLog(
        declaration_id=declaration.id,
        user_id=current_user.id,
        action="status_change",
        old_value={"status": old_status},
        new_value={"status": new_status.value},
    )
    db.add(log_entry)

    history_entry = DeclarationStatusHistory(
        declaration_id=declaration.id,
        status_code=new_status.value,
        status_text=f"Status changed from {old_status} to {new_status.value}",
        source="system",
    )
    db.add(history_entry)

    if force and override_reason:
        override_log = DeclarationLog(
            declaration_id=declaration.id,
            user_id=current_user.id,
            action="pre_send_gate_override",
            old_value={"reason": override_reason},
            new_value={"new_status": new_status.value},
        )
        db.add(override_log)

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
