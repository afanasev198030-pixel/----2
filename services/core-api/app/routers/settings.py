"""
API для системных настроек.
OpenAI ключ и другие настройки хранятся в PostgreSQL core.system_settings.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog
import httpx

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: str
    provider: Optional[str] = None
    base_url: Optional[str] = None


class ServiceStatus(BaseModel):
    name: str
    port: int
    status: str  # ok, error, unavailable
    detail: str = ""


class SettingsResponse(BaseModel):
    openai_api_key_set: bool  # backward compat
    openai_model: str  # backward compat
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    chromadb_status: str
    rag_available: bool
    ai_status: str
    ai_message: str
    services: list[ServiceStatus] = []
    db_stats: dict = {}


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(text("SELECT value FROM core.system_settings WHERE key = :key"), {"key": key})
    row = result.fetchone()
    return row[0] if row else None


async def _set_setting(db: AsyncSession, key: str, value: str):
    await db.execute(text("""
        INSERT INTO core.system_settings (key, value, updated_at) VALUES (:key, :value, now())
        ON CONFLICT (key) DO UPDATE SET value = :value, updated_at = now()
    """), {"key": key, "value": value})
    await db.commit()


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить текущие настройки системы."""
    openai_key = await _get_setting(db, "openai_api_key")
    openai_model = await _get_setting(db, "openai_model") or "gpt-4o"

    import os
    llm_provider = await _get_setting(db, "llm_provider") or os.environ.get("LLM_PROVIDER", "deepseek")
    llm_model = await _get_setting(db, "llm_model") or os.environ.get("LLM_MODEL", "deepseek-chat")

    # Check ai-service health
    ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
    chromadb_status = "unknown"
    rag_available = False
    ai_status = "unknown"
    ai_message = ""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{ai_url}/health")
            health_data = resp.json()
            rag_available = health_data.get("rag_available", False)
            chromadb_connected = health_data.get("chromadb_connected", False)
            llm_configured = health_data.get("llm_configured", health_data.get("openai_configured", False))
            chromadb_status = "connected" if chromadb_connected else "disconnected"

            # Use provider/model from ai-service health if available
            active_provider = health_data.get("llm_provider", llm_provider)
            active_model = health_data.get("llm_model", llm_model)
            provider_label = active_provider.capitalize()

            if llm_configured and rag_available:
                ai_status = "active"
                ai_message = f"AI работает: {provider_label} ({active_model}) + RAG"
            elif openai_key and not llm_configured:
                ai_status = "key_not_applied"
                ai_message = "Ключ сохранён, но не применён к AI-сервису. Нажмите Сохранить."
            elif not openai_key:
                ai_status = "no_key"
                ai_message = "API ключ не установлен. Используется regex-парсинг (базовая точность)."
            else:
                ai_status = "partial"
                ai_message = "AI частично работает."
    except Exception:
        chromadb_status = "unavailable"
        ai_status = "unavailable"
        ai_message = "AI-сервис недоступен"

    # Check ALL services
    services = []

    # core-api (self)
    services.append(ServiceStatus(name="core-api", port=8001, status="ok", detail="Ядро системы"))

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        services.append(ServiceStatus(name="PostgreSQL", port=5432, status="ok", detail="База данных"))
    except Exception:
        services.append(ServiceStatus(name="PostgreSQL", port=5432, status="error", detail="Не подключён"))

    # Redis (TCP check via Docker DNS)
    try:
        import socket
        redis_host = os.environ.get("REDIS_URL", "redis://redis:6379/0").split("://")[1].split(":")[0]
        s = socket.create_connection((redis_host, 6379), timeout=2)
        s.close()
        services.append(ServiceStatus(name="Redis", port=6379, status="ok", detail="Кеш и очереди"))
    except Exception:
        services.append(ServiceStatus(name="Redis", port=6379, status="error", detail="Не запущен"))

    # MinIO
    try:
        minio_host = os.environ.get("MINIO_ENDPOINT", "minio:9000").replace("http://", "").split(":")[0]
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"http://{minio_host}:9000/minio/health/live")
            services.append(ServiceStatus(name="MinIO", port=9000, status="ok" if r.status_code == 200 else "error", detail="Файловое хранилище S3"))
    except Exception:
        services.append(ServiceStatus(name="MinIO", port=9000, status="error", detail="Не запущен"))

    # file-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://file-service:8002/health")
            services.append(ServiceStatus(name="file-service", port=8002, status="ok", detail="Загрузка файлов"))
    except Exception:
        services.append(ServiceStatus(name="file-service", port=8002, status="error", detail="Не запущен"))

    # ai-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{ai_url}/health")
            d = r.json()
            detail = f"RAG={'OK' if d.get('rag_available') else 'OFF'}, OpenAI={'OK' if d.get('openai_configured') else 'OFF'}"
            services.append(ServiceStatus(name="ai-service", port=8003, status="ok", detail=detail))
    except Exception:
        services.append(ServiceStatus(name="ai-service", port=8003, status="error", detail="Не запущен"))

    # ChromaDB (internal port 8000, exposed as 8100)
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://chromadb:8000/api/v2/heartbeat")
            services.append(ServiceStatus(name="ChromaDB", port=8100, status="ok" if r.status_code == 200 else "error", detail="Векторная БД"))
    except Exception:
        services.append(ServiceStatus(name="ChromaDB", port=8100, status="error", detail="Не запущен"))

    # calc-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://calc-service:8005/health")
            services.append(ServiceStatus(name="calc-service", port=8005, status="ok", detail="Расчёт платежей, курсы ЦБ"))
    except Exception:
        services.append(ServiceStatus(name="calc-service", port=8005, status="error", detail="Не запущен"))

    # DB stats
    db_stats = {}
    try:
        r = await db.execute(text("SELECT count(*) FROM core.classifiers WHERE classifier_type='hs_code'"))
        db_stats["hs_codes"] = r.scalar() or 0
        r = await db.execute(text("SELECT count(*) FROM core.classifiers WHERE classifier_type!='hs_code'"))
        db_stats["classifiers"] = r.scalar() or 0
        r = await db.execute(text("SELECT count(*) FROM core.declarations"))
        db_stats["declarations"] = r.scalar() or 0
        r = await db.execute(text("SELECT count(*) FROM core.users"))
        db_stats["users"] = r.scalar() or 0
        r = await db.execute(text("SELECT count(*) FROM core.counterparties"))
        db_stats["counterparties"] = r.scalar() or 0
    except Exception:
        pass

    return SettingsResponse(
        openai_api_key_set=bool(openai_key),
        openai_model=openai_model,
        llm_provider=llm_provider,
        llm_model=llm_model,
        chromadb_status=chromadb_status,
        rag_available=rag_available,
        ai_status=ai_status,
        ai_message=ai_message,
        services=services,
        db_stats=db_stats,
    )


@router.post("/openai-key")
async def set_openai_key(
    data: SettingUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Установить LLM API ключ (DeepSeek/OpenAI). Сохраняется в БД. Обратная совместимость: key=openai_api_key."""
    if data.key not in ("openai_api_key", "llm_api_key"):
        raise HTTPException(status_code=400, detail="Invalid key")

    # Сохранить ключ в БД
    await _set_setting(db, "openai_api_key", data.value)
    await _set_setting(db, "llm_api_key", data.value)

    # Сохранить провайдера и base_url из запроса (если переданы)
    import os
    if data.provider:
        await _set_setting(db, "llm_provider", data.provider)
        llm_provider = data.provider
    else:
        llm_provider = await _get_setting(db, "llm_provider") or os.environ.get("LLM_PROVIDER", "deepseek")

    if data.base_url:
        await _set_setting(db, "llm_base_url", data.base_url)
        llm_base_url = data.base_url
    else:
        llm_base_url = await _get_setting(db, "llm_base_url") or os.environ.get("LLM_BASE_URL", "")

    llm_model = await _get_setting(db, "llm_model") or os.environ.get("LLM_MODEL", "")
    logger.info("llm_key_saved", user_id=str(current_user.id), provider=llm_provider)

    # Определить base_url для валидации
    if llm_base_url:
        validate_base_url = llm_base_url
    elif llm_provider == "openai":
        validate_base_url = "https://api.openai.com/v1"
    else:
        validate_base_url = "https://api.deepseek.com"

    # Определить модель для валидации
    if llm_model:
        validate_model = llm_model
    elif llm_provider == "openai":
        validate_model = "gpt-4o-mini"
    else:
        validate_model = "deepseek-chat"

    # Проверить ключ через ai-service (у core-api нет openai SDK)
    ai_check = {"status": "unknown", "message": ""}
    try:
        ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")
        async with httpx.AsyncClient(timeout=30) as validate_client:
            validate_resp = await validate_client.post(
                f"{ai_url}/api/v1/ai/configure",
                json={
                    "api_key": data.value,
                    "model": validate_model,
                    "base_url": validate_base_url,
                    "provider": llm_provider,
                    "openai_api_key": data.value,
                    "openai_model": validate_model,
                },
            )
            validate_data = validate_resp.json()
            if validate_data.get("openai_configured") or validate_data.get("llm_configured"):
                provider_label = llm_provider.capitalize()
                ai_check = {"status": "ok", "message": f"{provider_label} API ключ применён. AI работает."}
                logger.info("llm_key_applied", provider=llm_provider, model=validate_model)
            else:
                ai_check = {"status": "error", "message": f"Ключ сохранён, но AI-сервис не смог его применить."}
    except Exception as e:
        err_msg = str(e)
        ai_check = {"status": "error", "message": f"Ошибка проверки: {err_msg[:200]}"}
        logger.warning("llm_key_check_failed", error=err_msg[:100], provider=llm_provider)

    ai_result = {}

    return {
        "status": "saved",
        "key_set": True,
        "provider": llm_provider,
        "ai_check": ai_check,
        "ai_service_response": ai_result,
    }


@router.post("/openai-model")
async def set_openai_model(
    data: SettingUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Установить модель OpenAI."""
    if data.key != "openai_model":
        raise HTTPException(status_code=400, detail="Invalid key")

    await _set_setting(db, "openai_model", data.value)
    logger.info("openai_model_updated", model=data.value)
    return {"status": "saved", "model": data.value}


@router.post("/load-tnved")
async def load_tnved(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Загрузить коды ТН ВЭД в PostgreSQL из seed-данных."""
    try:
        # Check current count
        r = await db.execute(text("SELECT count(*) FROM core.classifiers WHERE classifier_type='hs_code'"))
        existing = r.scalar() or 0

        if existing > 500:
            return {"status": "exists", "count": existing, "message": f"Уже загружено {existing} кодов ТН ВЭД"}

        # Run seed loader inline
        from app.seeds.load_tnved import TNVED_GROUPS
        from app.models import Classifier
        from sqlalchemy import select

        loaded = 0
        for group_code, group_name, positions in TNVED_GROUPS:
            # Group (2-digit)
            result = await db.execute(
                select(Classifier).where(
                    Classifier.classifier_type == "hs_code",
                    Classifier.code == group_code,
                )
            )
            if not result.scalar_one_or_none():
                db.add(Classifier(
                    classifier_type="hs_code", code=group_code,
                    name_ru=group_name, parent_code="", is_active=True,
                ))
                loaded += 1

            # 4-digit positions
            for pos_code, pos_name in positions:
                result = await db.execute(
                    select(Classifier).where(
                        Classifier.classifier_type == "hs_code",
                        Classifier.code == pos_code,
                    )
                )
                if result.scalar_one_or_none():
                    continue
                db.add(Classifier(
                    classifier_type="hs_code", code=pos_code,
                    name_ru=pos_name, parent_code=group_code, is_active=True,
                ))
                loaded += 1

                # Generate 6-digit sub-positions (00-09)
                for sub in range(10):
                    sub_code = f"{pos_code}{sub:02d}"
                    db.add(Classifier(
                        classifier_type="hs_code", code=sub_code,
                        name_ru=f"{pos_name} ({sub_code})",
                        parent_code=pos_code, is_active=True,
                    ))
                    loaded += 1

                    # Generate 10-digit codes
                    for subsub in range(10):
                        code10 = f"{sub_code}{subsub:02d}00"
                        db.add(Classifier(
                            classifier_type="hs_code", code=code10,
                            name_ru=f"{pos_name} ({code10})",
                            parent_code=sub_code, is_active=True,
                        ))
                        loaded += 1

            if loaded % 5000 == 0:
                await db.commit()

        await db.commit()

        # Re-count
        r = await db.execute(text("SELECT count(*) FROM core.classifiers WHERE classifier_type='hs_code'"))
        total = r.scalar() or 0

        logger.info("tnved_loaded", loaded=loaded, total=total)
        return {"status": "loaded", "loaded": loaded, "total": total}

    except Exception as e:
        await db.rollback()
        logger.error("tnved_load_failed", error=str(e), exc_info=True)
        raise HTTPException(500, f"Ошибка загрузки ТН ВЭД: {str(e)}")


@router.post("/init-rag")
async def init_rag(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Отправить ВСЕ коды ТН ВЭД из PostgreSQL в ai-service батчами по 500."""
    import os
    ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")

    try:
        # Fetch ALL HS codes from DB
        r = await db.execute(text(
            "SELECT code, name_ru, parent_code FROM core.classifiers "
            "WHERE classifier_type='hs_code' AND is_active=true "
            "ORDER BY code"
        ))
        rows = r.fetchall()
        all_codes = [{"code": row[0], "name_ru": row[1] or "", "parent_code": row[2] or ""} for row in rows]

        if not all_codes:
            return {"status": "no_codes", "message": "Нет кодов ТН ВЭД в БД. Сначала загрузите."}

        # First batch with force=True to clear old data, rest with force=False (append)
        BATCH_SIZE = 200
        total_indexed = 0
        batches = [all_codes[i:i + BATCH_SIZE] for i in range(0, len(all_codes), BATCH_SIZE)]
        errors = []

        async with httpx.AsyncClient(timeout=120) as client:
            for idx, batch in enumerate(batches):
                try:
                    force = (idx == 0)  # clear only on first batch
                    resp = await client.post(
                        f"{ai_url}/api/v1/ai/index-hs-codes",
                        json={"codes": batch, "force": force},
                    )
                    result = resp.json()
                    total_indexed += result.get("count", len(batch))
                    logger.info("rag_batch_sent", batch=idx + 1, total_batches=len(batches), count=len(batch))
                except Exception as e:
                    errors.append(f"batch {idx + 1}: {str(e)[:100]}")
                    logger.warning("rag_batch_failed", batch=idx + 1, error=str(e)[:100])

        logger.info("rag_init_complete", total=len(all_codes), indexed=total_indexed, errors=len(errors))
        return {
            "status": "indexed",
            "codes_total": len(all_codes),
            "codes_indexed": total_indexed,
            "batches": len(batches),
            "errors": errors[:5] if errors else [],
        }

    except Exception as e:
        logger.error("rag_init_failed", error=str(e), exc_info=True)
        raise HTTPException(500, f"Ошибка индексации RAG: {str(e)}")


@router.get("/training-stats")
async def get_training_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Проксирование статистики обучения из ai-service + локальные данные."""
    import os
    ai_url = os.environ.get("AI_SERVICE_URL", "http://ai-service:8003")

    # DB stats
    db_stats = {}
    try:
        r = await db.execute(text("SELECT count(*) FROM core.classifiers WHERE classifier_type='hs_code'"))
        db_stats["hs_codes_pg"] = r.scalar() or 0
        r = await db.execute(text("SELECT count(*) FROM core.ml_feedback"))
        db_stats["feedback_pg"] = r.scalar() or 0
    except Exception:
        db_stats["hs_codes_pg"] = 0
        db_stats["feedback_pg"] = 0

    # AI service stats
    ai_stats = {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{ai_url}/api/v1/ai/training-stats")
            ai_stats = resp.json()
    except Exception as e:
        ai_stats = {"error": str(e)}

    return {
        "db": db_stats,
        "ai": ai_stats,
    }


@router.on_event("startup")
async def load_settings_on_startup():
    """Загрузить OpenAI ключ из БД при старте core-api и отправить в ai-service."""
    pass  # Будет вызвано из main.py


# ══════════════════════════════════════════════════════════════
# Parse Issues — сбор ошибок для batch-тестирования
# ══════════════════════════════════════════════════════════════

from app.models.parse_issue import ParseIssue
from sqlalchemy import select, func as sa_func, desc


class ParseIssueCreate(BaseModel):
    declaration_id: Optional[str] = None
    stage: str
    severity: str = "warning"
    message: str
    details: Optional[dict] = None


@router.post("/parse-issues", status_code=201)
async def create_parse_issue(data: ParseIssueCreate, db: AsyncSession = Depends(get_db)):
    """Приём проблемы от ai-service (без auth — внутренний вызов)."""
    import uuid as _uuid
    decl_id = None
    if data.declaration_id:
        try:
            decl_id = _uuid.UUID(data.declaration_id)
        except ValueError:
            pass
    issue = ParseIssue(
        declaration_id=decl_id,
        stage=data.stage,
        severity=data.severity,
        message=data.message,
        details=data.details,
    )
    db.add(issue)
    await db.commit()
    return {"status": "created", "id": str(issue.id)}


@router.get("/parse-issues")
async def list_parse_issues(
    severity: Optional[str] = None,
    stage: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Список проблем парсинга с фильтрами — для агента и UI."""
    query = select(ParseIssue).order_by(desc(ParseIssue.created_at)).limit(limit)
    if severity:
        query = query.where(ParseIssue.severity == severity)
    if stage:
        query = query.where(ParseIssue.stage == stage)
    if resolved is not None:
        query = query.where(ParseIssue.resolved == resolved)
    result = await db.execute(query)
    issues = result.scalars().all()
    return {
        "items": [
            {
                "id": str(i.id),
                "declaration_id": str(i.declaration_id) if i.declaration_id else None,
                "stage": i.stage,
                "severity": i.severity,
                "message": i.message,
                "details": i.details,
                "resolved": i.resolved,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in issues
        ],
        "total": len(issues),
    }


@router.get("/parse-issues/summary")
async def parse_issues_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Агрегация: сколько ошибок по stage/severity."""
    result = await db.execute(
        select(
            ParseIssue.stage,
            ParseIssue.severity,
            sa_func.count().label("count"),
        )
        .where(ParseIssue.resolved == False)
        .group_by(ParseIssue.stage, ParseIssue.severity)
    )
    rows = result.all()
    summary = {}
    totals = {"error": 0, "warning": 0, "info": 0}
    for stage, severity, count in rows:
        summary.setdefault(stage, {})[severity] = count
        totals[severity] = totals.get(severity, 0) + count
    return {"by_stage": summary, "totals": totals, "total": sum(totals.values())}


@router.post("/parse-issues/{issue_id}/resolve")
async def resolve_parse_issue(
    issue_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Пометить проблему как исправленную."""
    import uuid as _uuid
    result = await db.execute(select(ParseIssue).where(ParseIssue.id == _uuid.UUID(issue_id)))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(404, "Issue not found")
    issue.resolved = True
    await db.commit()
    return {"status": "resolved"}
