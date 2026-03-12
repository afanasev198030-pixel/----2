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
from app.models.hs_code_history import HsCodeHistory
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


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_diff(left, right) -> Optional[float]:
    left_f = _to_float(left)
    right_f = _to_float(right)
    if left_f is None or right_f is None:
        return None
    base = max(abs(left_f), abs(right_f), 0.01)
    return abs(left_f - right_f) / base


def _normalize_document_type(doc: Document) -> str:
    raw = (doc.doc_type or "").strip().lower()
    aliases = {
        "packing": "packing_list",
        "packing_list": "packing_list",
        "transport": "transport_doc",
        "transport_doc": "transport_doc",
        "awb": "transport_doc",
    }
    if raw in aliases:
        return aliases[raw]
    if raw in {
        "invoice",
        "contract",
        "packing_list",
        "transport_doc",
        "transport_invoice",
        "application_statement",
        "specification",
        "tech_description",
    }:
        return raw
    name = (doc.original_filename or "").lower()
    if "invoice" in name or "инвойс" in name:
        return "invoice" if "transport" not in name and "фрахт" not in name else "transport_invoice"
    if "contract" in name or "контракт" in name or "договор" in name:
        return "contract"
    if "packing" in name or "упаков" in name:
        return "packing_list"
    if "awb" in name or "waybill" in name or "наклад" in name or "cmr" in name:
        return "transport_doc"
    if "spec" in name or "спец" in name:
        return "specification"
    if "tech" in name or "тех" in name:
        return "tech_description"
    if "application" in name or "заявка" in name:
        return "application_statement"
    return "other"


def _doc_payload(doc: Optional[Document]) -> dict:
    if not doc or not isinstance(doc.parsed_data, dict):
        return {}
    return doc.parsed_data


def _first_doc(docs_by_type: dict[str, list[Document]], doc_type: str) -> Optional[Document]:
    docs = docs_by_type.get(doc_type) or []
    return docs[0] if docs else None


def _build_required_declaration_checks(declaration: Declaration) -> list[PreSendCheck]:
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

    return checks


async def _load_items_count(declaration_id: uuid.UUID, db: AsyncSession) -> int:
    items_result = await db.execute(
        select(func.count()).select_from(DeclarationItem).where(
            DeclarationItem.declaration_id == declaration_id
        )
    )
    return items_result.scalar() or 0


def _build_items_presence_checks(items_count: int) -> list[PreSendCheck]:
    if items_count == 0:
        return [
            PreSendCheck(
                code="NO_ITEMS",
                severity="error",
                field="items",
                blocking=True,
                message="Нет позиций товаров (графа 31/33)",
            )
        ]
    return []


async def _load_documents(declaration_id: uuid.UUID, db: AsyncSession) -> list[Document]:
    docs_result = await db.execute(
        select(Document).where(Document.declaration_id == declaration_id)
    )
    return list(docs_result.scalars().all())


def _group_documents_by_type(docs: list[Document]) -> dict[str, list[Document]]:
    docs_by_type: dict[str, list[Document]] = {}
    for doc in docs:
        docs_by_type.setdefault(_normalize_document_type(doc), []).append(doc)
    return docs_by_type


def _build_document_matrix_checks(
    declaration: Declaration,
    docs_count: int,
    docs_by_type: dict[str, list[Document]],
    items_count: int,
) -> tuple[list[PreSendCheck], bool]:
    checks: list[PreSendCheck] = []
    recognized_doc_types = sorted(t for t, items in docs_by_type.items() if items and t != "other")
    need_transport_doc = bool(
        declaration.transport_type_border
        or declaration.transport_at_border
        or declaration.transport_on_border_id
    )
    need_packing_list = bool(
        items_count > 1
        or declaration.total_packages_count
        or declaration.total_gross_weight
        or declaration.total_net_weight
    )

    if docs_count == 0:
        checks.append(PreSendCheck(
            code="NO_DOCUMENTS", severity="error", field="documents",
            blocking=True, message="Нет прикреплённых документов",
        ))
    if docs_count > 0 and not docs_by_type.get("invoice"):
        checks.append(PreSendCheck(
            code="MISSING_INVOICE_DOCUMENT",
            severity="error",
            field="documents",
            blocking=True,
            message="В пакете нет инвойса — проверьте состав приложенных документов",
        ))
    if docs_count > 0 and not docs_by_type.get("contract"):
        checks.append(PreSendCheck(
            code="MISSING_CONTRACT_DOCUMENT",
            severity="error",
            field="documents",
            blocking=True,
            message="В пакете нет контракта — отправка без договора запрещена",
        ))
    if docs_count > 0 and need_transport_doc and not docs_by_type.get("transport_doc"):
        checks.append(PreSendCheck(
            code="MISSING_TRANSPORT_DOCUMENT",
            severity="error",
            field="documents",
            blocking=True,
            message="Для выбранного вида перевозки нет транспортного документа",
        ))
    if docs_count > 0 and need_packing_list and not docs_by_type.get("packing_list"):
        checks.append(PreSendCheck(
            code="MISSING_PACKING_LIST",
            severity="warning",
            field="documents",
            blocking=False,
            message="Нет упаковочного листа — вес и количество мест будут сложнее подтвердить",
        ))

    logger.info(
        "pre_send_document_matrix_checked",
        declaration_id=str(declaration.id),
        docs_count=docs_count,
        recognized_doc_types=recognized_doc_types,
        need_transport_doc=need_transport_doc,
        need_packing_list=need_packing_list,
    )

    return checks, need_transport_doc


async def _load_item_rows(declaration_id: uuid.UUID, db: AsyncSession) -> list[DeclarationItem]:
    item_rows_result = await db.execute(
        select(DeclarationItem).where(
            DeclarationItem.declaration_id == declaration_id,
        )
    )
    return list(item_rows_result.scalars().all())


def _build_item_quality_checks(item_rows: list[DeclarationItem]) -> list[PreSendCheck]:
    no_hs_count = sum(1 for item in item_rows if not (item.hs_code or "").strip())
    if no_hs_count > 0:
        return [
            PreSendCheck(
                code="ITEMS_WITHOUT_HS",
                severity="error",
                field="hs_code",
                blocking=True,
                message=f"{no_hs_count} позиций без кода ТН ВЭД",
            )
        ]
    return []


async def _load_blocking_issue_count(declaration_id: uuid.UUID, db: AsyncSession) -> int:
    blocking_issues = await db.execute(
        select(func.count()).select_from(ParseIssue).where(
            ParseIssue.declaration_id == declaration_id,
            ParseIssue.blocking.is_(True),
            ParseIssue.resolved.is_(False),
        )
    )
    return blocking_issues.scalar() or 0


def _build_issue_checks(
    declaration: Declaration,
    blocking_issue_count: int,
) -> list[PreSendCheck]:
    checks: list[PreSendCheck] = []

    if blocking_issue_count > 0:
        checks.append(PreSendCheck(
            code="BLOCKING_ISSUES", severity="error", field="ai_issues",
            blocking=True, message=f"{blocking_issue_count} нерешённых блокирующих проблем парсинга",
        ))

    if declaration.ai_issues:
        ai_blocking = [i for i in declaration.ai_issues if i.get("blocking") and not i.get("resolved")]
        if ai_blocking:
            checks.append(PreSendCheck(
                code="AI_BLOCKING_ISSUES", severity="error", field="ai_issues",
                blocking=True, message=f"{len(ai_blocking)} блокирующих AI-проблем",
            ))

    return checks


def _build_cross_document_checks(
    declaration: Declaration,
    docs_by_type: dict[str, list[Document]],
    items_count: int,
    need_transport_doc: bool,
) -> tuple[list[PreSendCheck], dict[str, bool]]:
    checks: list[PreSendCheck] = []

    invoice_doc = _first_doc(docs_by_type, "invoice")
    contract_doc = _first_doc(docs_by_type, "contract")
    packing_doc = _first_doc(docs_by_type, "packing_list")
    transport_doc = _first_doc(docs_by_type, "transport_doc")

    invoice_payload = _doc_payload(invoice_doc)
    contract_payload = _doc_payload(contract_doc)
    packing_payload = _doc_payload(packing_doc)

    invoice_total = _to_float(invoice_payload.get("total_amount"))
    declaration_total = _to_float(declaration.total_invoice_value)
    total_diff_pct = _pct_diff(invoice_total, declaration_total)
    if total_diff_pct is not None and total_diff_pct > 0.05:
        checks.append(PreSendCheck(
            code="INVOICE_TOTAL_MISMATCH",
            severity="warning",
            field="total_invoice_value",
            blocking=False,
            message=(
                f"Сумма в декларации ({declaration_total:.2f}) отличается от суммы инвойса "
                f"({invoice_total:.2f}) на {total_diff_pct:.0%}"
            ),
        ))

    contract_currency = (contract_payload.get("currency") or "").strip().upper()
    declaration_currency = (declaration.currency_code or "").strip().upper()
    if contract_currency and declaration_currency and contract_currency != declaration_currency:
        checks.append(PreSendCheck(
            code="CONTRACT_CURRENCY_MISMATCH",
            severity="error",
            field="currency_code",
            blocking=True,
            message=(
                f"Валюта декларации ({declaration_currency}) не совпадает с валютой договора "
                f"({contract_currency})"
            ),
        ))

    invoice_currency = (invoice_payload.get("currency") or "").strip().upper()
    if invoice_currency and declaration_currency and invoice_currency != declaration_currency:
        checks.append(PreSendCheck(
            code="INVOICE_CURRENCY_MISMATCH",
            severity="warning",
            field="currency_code",
            blocking=False,
            message=(
                f"Валюта инвойса ({invoice_currency}) отличается от валюты декларации "
                f"({declaration_currency})"
            ),
        ))

    packing_gross = _to_float(packing_payload.get("total_gross_weight"))
    declaration_gross = _to_float(declaration.total_gross_weight)
    gross_diff_pct = _pct_diff(packing_gross, declaration_gross)
    if gross_diff_pct is not None and gross_diff_pct > 0.05:
        checks.append(PreSendCheck(
            code="PACKING_GROSS_MISMATCH",
            severity="warning",
            field="total_gross_weight",
            blocking=False,
            message=(
                f"Вес брутто в декларации ({declaration_gross:.3f}) отличается от packing list "
                f"({packing_gross:.3f}) на {gross_diff_pct:.0%}"
            ),
        ))

    packing_net = _to_float(packing_payload.get("total_net_weight"))
    declaration_net = _to_float(declaration.total_net_weight)
    net_diff_pct = _pct_diff(packing_net, declaration_net)
    if net_diff_pct is not None and net_diff_pct > 0.05:
        checks.append(PreSendCheck(
            code="PACKING_NET_MISMATCH",
            severity="warning",
            field="total_net_weight",
            blocking=False,
            message=(
                f"Вес нетто в декларации ({declaration_net:.3f}) отличается от packing list "
                f"({packing_net:.3f}) на {net_diff_pct:.0%}"
            ),
        ))

    packing_packages = packing_payload.get("total_packages")
    declaration_packages = declaration.total_packages_count
    if packing_packages and declaration_packages and int(packing_packages) != int(declaration_packages):
        checks.append(PreSendCheck(
            code="PACKING_PACKAGES_MISMATCH",
            severity="warning",
            field="total_packages_count",
            blocking=False,
            message=(
                f"Количество мест в декларации ({declaration_packages}) отличается от packing list "
                f"({packing_packages})"
            ),
        ))

    invoice_items = invoice_payload.get("items")
    if isinstance(invoice_items, list) and items_count and len(invoice_items) != items_count:
        checks.append(PreSendCheck(
            code="INVOICE_ITEMS_COUNT_MISMATCH",
            severity="warning",
            field="items",
            blocking=False,
            message=(
                f"Количество позиций в декларации ({items_count}) отличается от количества позиций "
                f"в инвойсе ({len(invoice_items)})"
            ),
        ))

    if transport_doc and need_transport_doc and not (declaration.transport_at_border or declaration.transport_on_border_id):
        checks.append(PreSendCheck(
            code="TRANSPORT_DOC_NOT_APPLIED",
            severity="warning",
            field="transport_doc_number",
            blocking=False,
            message="Транспортный документ приложен, но его реквизиты не перенесены в декларацию",
        ))

    return checks, {
        "invoice_doc": bool(invoice_doc),
        "contract_doc": bool(contract_doc),
        "packing_doc": bool(packing_doc),
        "transport_doc": bool(transport_doc),
    }


async def _build_history_drift_checks(
    declaration: Declaration,
    item_rows: list[DeclarationItem],
    db: AsyncSession,
) -> tuple[list[PreSendCheck], int]:
    checks: list[PreSendCheck] = []
    drift_warnings = 0

    for item in item_rows:
        current_hs = (item.hs_code or "").strip()
        desc_norm = ((item.description or item.commercial_name or "").strip().lower())[:300]
        if not current_hs or not desc_norm:
            continue

        similarity_expr = func.similarity(HsCodeHistory.description_trgm, desc_norm)
        history_result = await db.execute(
            select(
                HsCodeHistory.hs_code,
                HsCodeHistory.usage_count,
                similarity_expr.label("similarity"),
            ).where(
                HsCodeHistory.company_id == declaration.company_id,
                HsCodeHistory.description_trgm.is_not(None),
                similarity_expr > 0.35,
            ).order_by(
                similarity_expr.desc(),
                HsCodeHistory.usage_count.desc(),
            ).limit(20)
        )
        rows = list(history_result.all())
        if not rows:
            continue

        aggregated: dict[str, dict[str, float]] = {}
        for hs_code, usage_count, similarity in rows:
            entry = aggregated.setdefault(hs_code, {"usage": 0.0, "similarity": 0.0})
            entry["usage"] += float(usage_count or 0)
            entry["similarity"] = max(entry["similarity"], float(similarity or 0.0))

        leader_hs, leader_data = max(
            aggregated.items(),
            key=lambda pair: (pair[1]["usage"], pair[1]["similarity"]),
        )
        current_data = aggregated.get(current_hs)
        if leader_hs == current_hs:
            continue
        if leader_data["usage"] < 3 or leader_data["similarity"] < 0.55:
            continue
        if current_data and leader_data["usage"] < current_data["usage"] + 2:
            continue

        drift_warnings += 1
        item_no = item.item_no or drift_warnings
        checks.append(PreSendCheck(
            code="HS_HISTORY_DRIFT",
            severity="warning",
            field="hs_code",
            blocking=False,
            message=(
                f"Позиция {item_no}: текущий код {current_hs} расходится с устойчивой историей компании. "
                f"По похожим описаниям чаще использовался {leader_hs} "
                f"(использований: {int(leader_data['usage'])}, similarity: {leader_data['similarity']:.2f})."
            ),
        ))

    logger.info(
        "pre_send_history_drift_checked",
        declaration_id=str(declaration.id),
        items_checked=len(item_rows),
        drift_warnings=drift_warnings,
    )

    return checks, drift_warnings


def _build_weight_consistency_checks(declaration: Declaration) -> list[PreSendCheck]:
    if declaration.total_gross_weight and declaration.total_net_weight:
        if declaration.total_net_weight > declaration.total_gross_weight:
            return [
                PreSendCheck(
                    code="WEIGHT_INCONSISTENCY",
                    severity="warning",
                    field="total_net_weight",
                    blocking=False,
                    message="Вес нетто превышает вес брутто",
                )
            ]
    return []


async def run_pre_send_checks(
    declaration: Declaration, db: AsyncSession
) -> PreSendResult:
    """Server-side validation before allowing send/sign transitions."""
    checks: list[PreSendCheck] = []
    checks.extend(_build_required_declaration_checks(declaration))

    items_count = await _load_items_count(declaration.id, db)
    checks.extend(_build_items_presence_checks(items_count))

    docs = await _load_documents(declaration.id, db)
    docs_count = len(docs)
    docs_by_type = _group_documents_by_type(docs)
    document_checks, need_transport_doc = _build_document_matrix_checks(
        declaration,
        docs_count,
        docs_by_type,
        items_count,
    )
    checks.extend(document_checks)

    item_rows = await _load_item_rows(declaration.id, db)
    checks.extend(_build_item_quality_checks(item_rows))

    blocking_count = await _load_blocking_issue_count(declaration.id, db)
    checks.extend(_build_issue_checks(declaration, blocking_count))

    cross_doc_checks, cross_doc_log_payload = _build_cross_document_checks(
        declaration,
        docs_by_type,
        items_count,
        need_transport_doc,
    )
    checks.extend(cross_doc_checks)

    history_drift_checks, _ = await _build_history_drift_checks(declaration, item_rows, db)
    checks.extend(history_drift_checks)

    logger.info(
        "pre_send_cross_doc_checked",
        declaration_id=str(declaration.id),
        **cross_doc_log_payload,
    )

    checks.extend(_build_weight_consistency_checks(declaration))

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


@router.post("/status", response_model=dict)
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
