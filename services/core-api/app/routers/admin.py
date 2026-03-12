"""Admin endpoints: audit log, user details with audit, classifier sync."""
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
import structlog

from app.database import get_db
from app.middleware.auth import require_role
from app.models import User, UserRole, ClassifierSyncLog
from app.models.ai_usage_log import AiUsageLog
from app.models.audit_log import AuditLog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/audit")
async def get_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    user_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get audit log with filters (admin only)."""
    query = select(AuditLog).options(selectinload(AuditLog.user))
    count_query = select(func.count()).select_from(AuditLog)

    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return {
        "items": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "user_email": log.user.email if log.user else None,
                "user_name": log.user.full_name if log.user else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/audit/actions")
async def get_audit_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get list of unique actions in audit log."""
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    return [r[0] for r in result.all()]


@router.get("/users/{user_id}/audit")
async def get_user_audit(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get audit log for specific user."""
    query = select(AuditLog).where(AuditLog.user_id == user_id)
    count_query = select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page)
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# Classifier sync endpoints
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    classifier_types: Optional[list[str]] = None
    force_full: bool = False


class AITrainingSyncRequest(BaseModel):
    declaration_limit: int = 200


@router.post("/classifiers-sync")
async def trigger_classifier_sync(
    body: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Trigger classifier synchronization from portal.eaeunion.org.

    Runs in the background so the request returns immediately.
    """
    from app.services.classifier_sync import full_sync, incremental_sync, sync_all
    from app.services.eec_classifier_config import EEC_CLASSIFIERS

    if body.classifier_types:
        unknown = [t for t in body.classifier_types if t not in EEC_CLASSIFIERS]
        if unknown:
            raise HTTPException(400, f"Unknown classifier types: {unknown}")

    async def _run_sync():
        if body.classifier_types:
            for ct in body.classifier_types:
                if body.force_full:
                    await full_sync(ct)
                else:
                    await incremental_sync(ct)
        else:
            await sync_all(force_full=body.force_full)

    background_tasks.add_task(_run_sync)

    return {
        "status": "started",
        "classifier_types": body.classifier_types or list(EEC_CLASSIFIERS.keys()),
        "force_full": body.force_full,
    }


@router.post("/ai-training-sync")
async def trigger_ai_training_sync(
    body: AITrainingSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Запустить сбор и отправку обучающих примеров ТН ВЭД в ai-service."""
    from app.config import settings
    from app.database import async_sessionmaker
    from app.services.ai_training import run_hs_training_sync

    declaration_limit = max(10, min(body.declaration_limit, 2000))

    async def _run_training_sync():
        try:
            async with async_sessionmaker() as session:
                await run_hs_training_sync(
                    db=session,
                    ai_service_url=settings.AI_SERVICE_URL,
                    limit_declarations=declaration_limit,
                )
        except Exception as exc:
            logger.error("ai_training_sync_failed", error=str(exc), exc_info=True)

    background_tasks.add_task(_run_training_sync)
    return {"status": "started", "declaration_limit": declaration_limit}


@router.get("/classifiers-sync/status")
async def get_classifier_sync_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get the latest sync status for each classifier type."""
    from app.services.eec_classifier_config import EEC_CLASSIFIERS

    subq = (
        select(
            ClassifierSyncLog.classifier_type,
            func.max(ClassifierSyncLog.last_sync_at).label("max_sync"),
        )
        .group_by(ClassifierSyncLog.classifier_type)
        .subquery()
    )
    query = (
        select(ClassifierSyncLog)
        .join(
            subq,
            and_(
                ClassifierSyncLog.classifier_type == subq.c.classifier_type,
                ClassifierSyncLog.last_sync_at == subq.c.max_sync,
            ),
        )
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    log_map = {log.classifier_type: log for log in logs}

    items = []
    for ct, cfg in EEC_CLASSIFIERS.items():
        log = log_map.get(ct)
        items.append({
            "classifier_type": ct,
            "title": cfg["title"],
            "last_sync_at": log.last_sync_at.isoformat() if log else None,
            "last_modification_check": log.last_modification_check.isoformat() if log and log.last_modification_check else None,
            "records_total": log.records_total if log else 0,
            "records_updated": log.records_updated if log else 0,
            "status": log.status if log else "never",
            "error_message": log.error_message if log else None,
        })

    return {"items": items}


@router.get("/classifiers-sync/log")
async def get_classifier_sync_log(
    classifier_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get sync history log, optionally filtered by classifier type."""
    query = select(ClassifierSyncLog)
    count_query = select(func.count()).select_from(ClassifierSyncLog)

    if classifier_type:
        query = query.where(ClassifierSyncLog.classifier_type == classifier_type)
        count_query = count_query.where(ClassifierSyncLog.classifier_type == classifier_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    query = query.order_by(ClassifierSyncLog.last_sync_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(log.id),
                "classifier_type": log.classifier_type,
                "eec_guid": log.eec_guid,
                "last_sync_at": log.last_sync_at.isoformat() if log.last_sync_at else None,
                "last_modification_check": log.last_modification_check.isoformat() if log.last_modification_check else None,
                "records_total": log.records_total,
                "records_updated": log.records_updated,
                "status": log.status,
                "error_message": log.error_message,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/ai-costs")
async def get_ai_costs(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Дашборд unit-экономики AI (Phase 4.3)."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)

    totals = await db.execute(
        select(
            func.count(AiUsageLog.id).label("total_calls"),
            func.coalesce(func.sum(AiUsageLog.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(AiUsageLog.output_tokens), 0).label("total_output"),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AiUsageLog.cost_usd), 0).label("total_cost"),
            func.coalesce(func.avg(AiUsageLog.duration_ms), 0).label("avg_duration_ms"),
        ).where(AiUsageLog.created_at >= since)
    )
    row = totals.one()

    by_operation = await db.execute(
        select(
            AiUsageLog.operation,
            func.count(AiUsageLog.id).label("calls"),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AiUsageLog.cost_usd), 0).label("cost"),
        ).where(AiUsageLog.created_at >= since)
        .group_by(AiUsageLog.operation)
        .order_by(func.sum(AiUsageLog.cost_usd).desc())
    )

    by_model = await db.execute(
        select(
            AiUsageLog.model,
            func.count(AiUsageLog.id).label("calls"),
            func.coalesce(func.sum(AiUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AiUsageLog.cost_usd), 0).label("cost"),
        ).where(AiUsageLog.created_at >= since)
        .group_by(AiUsageLog.model)
        .order_by(func.sum(AiUsageLog.cost_usd).desc())
    )

    decl_count = await db.execute(
        select(func.count(func.distinct(AiUsageLog.declaration_id)))
        .where(AiUsageLog.created_at >= since, AiUsageLog.declaration_id.isnot(None))
    )
    unique_decls = decl_count.scalar() or 0
    cost_per_decl = float(row.total_cost) / unique_decls if unique_decls > 0 else 0

    return {
        "period_days": days,
        "totals": {
            "calls": row.total_calls,
            "input_tokens": row.total_input,
            "output_tokens": row.total_output,
            "total_tokens": row.total_tokens,
            "cost_usd": round(float(row.total_cost), 4),
            "avg_duration_ms": round(float(row.avg_duration_ms)),
        },
        "unit_economics": {
            "declarations_processed": unique_decls,
            "cost_per_declaration_usd": round(cost_per_decl, 4),
        },
        "by_operation": [
            {"operation": r.operation, "calls": r.calls, "tokens": r.tokens, "cost_usd": round(float(r.cost), 4)}
            for r in by_operation
        ],
        "by_model": [
            {"model": r.model, "calls": r.calls, "tokens": r.tokens, "cost_usd": round(float(r.cost), 4)}
            for r in by_model
        ],
    }
