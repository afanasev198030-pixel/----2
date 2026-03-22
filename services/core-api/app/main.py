import asyncio

from fastapi import FastAPI, Request, HTTPException, status, Depends
from app.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.config import settings
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.logging import setup_logging
from app.models.declaration import Declaration
from app.routers import (
    auth,
    declarations,
    declaration_items,
    workflow,
    documents,
    classifiers,
    users,
    telegram,
)
from app.routers import apply_parsed, broker_clients
from app.routers import settings as settings_router
from app.routers import counterparties, companies
from app.routers import export_pdf
from app.routers import admin as admin_router
from app.routers import knowledge as knowledge_router
from app.routers import graph_rules as graph_rules_router
from app.routers import ai_strategies as ai_strategies_router
from app.routers import hs_history as hs_history_router
from app.routers import item_documents as item_documents_router
from app.routers import item_preceding_docs as item_preceding_docs_router
from app.routers import customs_value as customs_value_router

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Customs Declaration API",
    version="0.1.0",
    description="API for automated customs declaration system",
)


@app.on_event("startup")
async def startup_event():
    """Log service start. Load OpenAI key from DB."""
    logger.info(
        "service_started",
        service_name=settings.SERVICE_NAME,
        version="0.1.0",
    )

    # Load LLM key and provider from DB and send to ai-service (DeepSeek/OpenAI)
    try:
        from app.database import async_sessionmaker
        from sqlalchemy import text
        import httpx
        import os

        async with async_sessionmaker() as session:
            rows = await session.execute(text(
                "SELECT key, value FROM core.system_settings WHERE key IN "
                "('openai_api_key', 'llm_api_key', 'llm_provider', 'llm_model', 'openai_model', 'llm_base_url', 'llm_project_id')"
            ))
            settings_map = {r[0]: r[1] for r in rows.fetchall() if r[1]}
            api_key = (settings_map.get("openai_api_key") or settings_map.get("llm_api_key") or "").strip()
            if not api_key or api_key == "sk-your-key-here":
                logger.info("no_openai_key_in_db")
            else:
                provider = settings_map.get("llm_provider") or os.environ.get("LLM_PROVIDER", "deepseek")
                model = settings_map.get("llm_model") or settings_map.get("openai_model") or ""
                base_url = settings_map.get("llm_base_url") or ""
                project_id = settings_map.get("llm_project_id") or ""
                model_defaults = {"deepseek": "deepseek-chat", "cloud_ru": "openai/gpt-oss-120b"}
                if not model:
                    model = model_defaults.get(provider, "gpt-4o")
                url_defaults = {"deepseek": "https://api.deepseek.com", "cloud_ru": "https://foundation-models.api.cloud.ru/v1"}
                if not base_url:
                    base_url = url_defaults.get(provider, "https://api.openai.com/v1")
                logger.info("openai_key_loaded_from_db", key_prefix=api_key[:8] + "...", provider=provider, model=model)
                ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(
                        f"{ai_url}/api/v1/ai/configure",
                        json={
                            "openai_api_key": api_key,
                            "openai_model": model,
                            "api_key": api_key,
                            "model": model,
                            "provider": provider,
                            "base_url": base_url,
                            "project_id": project_id,
                        },
                    )
                    logger.info("openai_key_sent_to_ai_service", provider=provider, model=model)
    except Exception as e:
        logger.warning("startup_key_load_failed", error=str(e))

    # Start periodic classifier sync from portal.eaeunion.org
    if settings.EEC_SYNC_ENABLED:
        asyncio.create_task(_classifier_sync_loop())
        logger.info("eec_classifier_sync_scheduler_started",
                     interval_hours=settings.EEC_SYNC_INTERVAL_HOURS)

    if settings.AI_TRAINING_SYNC_ENABLED:
        asyncio.create_task(_ai_training_sync_loop())
        logger.info(
            "ai_training_sync_scheduler_started",
            interval_hours=settings.AI_TRAINING_SYNC_INTERVAL_HOURS,
            declaration_limit=settings.AI_TRAINING_SYNC_DECL_LIMIT,
        )


async def _classifier_sync_loop():
    """Background loop that syncs EEC classifiers on a schedule."""
    await asyncio.sleep(60)
    while True:
        try:
            from app.services.classifier_sync import sync_all
            results = await sync_all(force_full=False)
            ok = sum(1 for r in results.values() if r.status == "success")
            err = sum(1 for r in results.values() if r.status == "error")
            logger.info("eec_scheduled_sync_done", success=ok, errors=err)
        except Exception as exc:
            logger.error("eec_scheduled_sync_failed", error=str(exc))

        await asyncio.sleep(settings.EEC_SYNC_INTERVAL_HOURS * 3600)


async def _ai_training_sync_loop():
    """Background loop for syncing approved HS examples into ai-service."""
    await asyncio.sleep(90)
    while True:
        try:
            from app.database import async_sessionmaker
            from app.services.ai_training import run_hs_training_sync

            async with async_sessionmaker() as session:
                result = await run_hs_training_sync(
                    db=session,
                    ai_service_url=settings.AI_SERVICE_URL,
                    limit_declarations=settings.AI_TRAINING_SYNC_DECL_LIMIT,
                )
            logger.info(
                "ai_training_scheduled_sync_done",
                prepared_examples=result.prepared_examples,
                sent_examples=result.sent_examples,
                dropped_examples=result.dropped_examples,
            )
        except Exception as exc:
            logger.error("ai_training_scheduled_sync_failed", error=str(exc), exc_info=True)

        await asyncio.sleep(settings.AI_TRAINING_SYNC_INTERVAL_HOURS * 3600)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that catches all exceptions."""
    # Log the error
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
        exc_info=True,
    )
    
    # If it's already an HTTPException, re-raise it
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_type": type(exc).__name__,
            },
        )
    
    # For other exceptions, return 500
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "error_message": str(exc) if settings.LOG_LEVEL == "DEBUG" else "An error occurred",
        },
    )


# Health check endpoint (liveness — always 200 if process is alive)
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "core-api"}


# Readiness check (checks real dependencies before accepting traffic)
@app.get("/ready")
async def readiness_check():
    checks = {}
    all_ok = True

    # PostgreSQL
    try:
        from app.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as e:
        checks["postgres"] = {"status": "error", "detail": str(e)[:200]}
        all_ok = False

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "detail": str(e)[:200]}
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "unavailable",
            "service": "core-api",
            "checks": checks,
        },
    )


# Internal endpoint for ai-service (no auth)
@app.post("/api/v1/internal/parse-issue", status_code=201)
async def internal_create_parse_issue(data: dict, db=Depends(get_db)):
    """Приём проблемы от ai-service — без авторизации."""
    from app.models.parse_issue import ParseIssue
    import uuid as _uuid
    decl_id = None
    if data.get("declaration_id"):
        try:
            decl_id = _uuid.UUID(data["declaration_id"])
        except (ValueError, TypeError):
            pass
    issue = ParseIssue(
        declaration_id=decl_id,
        stage=data.get("stage", "unknown"),
        severity=data.get("severity", "warning"),
        message=data.get("message", ""),
        details=data.get("details"),
    )
    db.add(issue)
    await db.commit()
    return {"status": "created", "id": str(issue.id)}


@app.post("/api/v1/internal/task-complete", status_code=200)
async def internal_task_complete(data: dict, db=Depends(get_db)):
    """Callback from ai-worker when background parsing task completes."""
    import uuid as _uuid
    declaration_id = data.get("declaration_id")
    task_status = data.get("status", "unknown")
    request_id = data.get("request_id")

    if not declaration_id:
        return {"status": "ignored", "reason": "no declaration_id"}

    try:
        decl_uuid = _uuid.UUID(declaration_id)
    except (ValueError, TypeError):
        return {"status": "ignored", "reason": "invalid declaration_id"}

    from sqlalchemy import select
    result = await db.execute(select(Declaration).where(Declaration.id == decl_uuid))
    decl = result.scalar_one_or_none()
    if decl:
        decl.processing_status = "complete" if task_status == "success" else "failed"
        await db.commit()
        logger.info(
            "task_complete_callback",
            declaration_id=declaration_id,
            processing_status=decl.processing_status,
            request_id=request_id,
        )
    return {"status": "ok"}


@app.post("/api/v1/internal/apply-parsed/{declaration_id}", status_code=200)
async def internal_apply_parsed(declaration_id: str, data: dict, db=Depends(get_db)):
    """Worker callback: apply parsed AI result to declaration without JWT auth."""
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import User

    try:
        decl_uuid = _uuid.UUID(declaration_id)
    except (ValueError, TypeError):
        return {"status": "error", "reason": "invalid declaration_id"}

    result = await db.execute(select(Declaration).where(Declaration.id == decl_uuid))
    decl = result.scalar_one_or_none()
    if not decl:
        return {"status": "error", "reason": "declaration not found"}

    user_result = await db.execute(select(User).where(User.id == decl.created_by))
    user = user_result.scalar_one_or_none()
    if not user:
        return {"status": "error", "reason": "creator user not found"}

    try:
        from app.routers.apply_parsed import apply_parsed_data, ApplyParsedRequest
        parsed_request = ApplyParsedRequest(**data)
        response = await apply_parsed_data(decl_uuid, parsed_request, db, user)
        logger.info(
            "internal_apply_parsed_ok",
            declaration_id=declaration_id,
            items=response.counters.get("items", 0) if hasattr(response, "counters") else "?",
        )
        return {"status": "ok"}
    except HTTPException as he:
        logger.warning("internal_apply_parsed_http_error", detail=he.detail, status=he.status_code)
        return {"status": "error", "reason": he.detail}
    except Exception as e:
        logger.exception("internal_apply_parsed_failed", error=str(e)[:300])
        return {"status": "error", "reason": str(e)[:300]}


@app.post("/api/v1/internal/ai-usage", status_code=201)
async def internal_ai_usage(data: dict, db=Depends(get_db)):
    """Приём данных о использовании AI-токенов от ai-service."""
    from app.models.ai_usage_log import AiUsageLog
    import uuid as _uuid
    from decimal import Decimal

    company_id = None
    declaration_id = None
    if data.get("company_id"):
        try:
            company_id = _uuid.UUID(data["company_id"])
        except (ValueError, TypeError):
            pass
    if data.get("declaration_id"):
        try:
            declaration_id = _uuid.UUID(data["declaration_id"])
        except (ValueError, TypeError):
            pass

    log = AiUsageLog(
        company_id=company_id,
        declaration_id=declaration_id,
        operation=data.get("operation", "unknown"),
        model=data.get("model", "unknown"),
        provider=data.get("provider", "unknown"),
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
        total_tokens=data.get("total_tokens", 0),
        cost_usd=Decimal(str(data.get("cost_usd", 0))) if data.get("cost_usd") else None,
        duration_ms=data.get("duration_ms"),
    )
    db.add(log)
    await db.commit()
    return {"status": "created"}


# Include routers
app.include_router(auth.router)
app.include_router(declarations.router)
app.include_router(declaration_items.router)
app.include_router(workflow.router)
app.include_router(documents.router)
app.include_router(classifiers.router)
app.include_router(users.router)
app.include_router(apply_parsed.router)
app.include_router(settings_router.router)
app.include_router(counterparties.router)
app.include_router(companies.router)
app.include_router(export_pdf.router)
app.include_router(broker_clients.router)
app.include_router(admin_router.router)
app.include_router(knowledge_router.router)
app.include_router(graph_rules_router.router)
app.include_router(ai_strategies_router.router)
app.include_router(hs_history_router.router)
app.include_router(item_documents_router.router)
app.include_router(item_preceding_docs_router.router)
app.include_router(customs_value_router.router)
app.include_router(telegram.router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
