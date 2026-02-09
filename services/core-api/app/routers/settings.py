"""
API для системных настроек.
OpenAI ключ и другие настройки хранятся в PostgreSQL core.system_settings.
"""
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


class ServiceStatus(BaseModel):
    name: str
    port: int
    status: str  # ok, error, unavailable
    detail: str = ""


class SettingsResponse(BaseModel):
    openai_api_key_set: bool
    openai_model: str
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

    # Check ai-service health
    chromadb_status = "unknown"
    rag_available = False
    ai_status = "unknown"
    ai_message = ""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:8003/health")
            data = resp.json()
            rag_available = data.get("rag_available", False)
            chromadb_connected = data.get("chromadb_connected", False)
            openai_configured = data.get("openai_configured", False)
            chromadb_status = "connected" if chromadb_connected else "disconnected"

            if openai_configured and rag_available:
                ai_status = "active"
                ai_message = "AI работает: GPT-4o + RAG"
            elif openai_key and not openai_configured:
                ai_status = "key_not_applied"
                ai_message = "Ключ сохранён, но не применён к AI-сервису. Нажмите Сохранить."
            elif not openai_key:
                ai_status = "no_key"
                ai_message = "OpenAI ключ не установлен. Используется regex-парсинг (базовая точность)."
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

    # Redis
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get("http://localhost:6379")
        services.append(ServiceStatus(name="Redis", port=6379, status="ok", detail="Кеш и очереди"))
    except Exception:
        # Redis doesn't have HTTP, check via tcp hint
        import socket
        try:
            s = socket.create_connection(("localhost", 6379), timeout=2)
            s.close()
            services.append(ServiceStatus(name="Redis", port=6379, status="ok", detail="Кеш и очереди"))
        except Exception:
            services.append(ServiceStatus(name="Redis", port=6379, status="error", detail="Не запущен"))

    # MinIO
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:9000/minio/health/live")
            services.append(ServiceStatus(name="MinIO", port=9000, status="ok" if r.status_code == 200 else "error", detail="Файловое хранилище S3"))
    except Exception:
        services.append(ServiceStatus(name="MinIO", port=9000, status="error", detail="Не запущен"))

    # file-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:8002/health")
            services.append(ServiceStatus(name="file-service", port=8002, status="ok", detail="Загрузка файлов"))
    except Exception:
        services.append(ServiceStatus(name="file-service", port=8002, status="error", detail="Не запущен"))

    # ai-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:8003/health")
            d = r.json()
            detail = f"RAG={'OK' if d.get('rag_available') else 'OFF'}, OpenAI={'OK' if d.get('openai_configured') else 'OFF'}"
            services.append(ServiceStatus(name="ai-service", port=8003, status="ok", detail=detail))
    except Exception:
        services.append(ServiceStatus(name="ai-service", port=8003, status="error", detail="Не запущен"))

    # ChromaDB
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:8100/api/v2/heartbeat")
            services.append(ServiceStatus(name="ChromaDB", port=8100, status="ok" if r.status_code == 200 else "error", detail="Векторная БД"))
    except Exception:
        services.append(ServiceStatus(name="ChromaDB", port=8100, status="error", detail="Не запущен"))

    # calc-service
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get("http://localhost:8005/health")
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
    """Установить OpenAI API ключ. Сохраняется в БД."""
    if data.key != "openai_api_key":
        raise HTTPException(status_code=400, detail="Invalid key")

    # Сохранить в БД
    await _set_setting(db, "openai_api_key", data.value)
    logger.info("openai_key_saved_to_db", user_id=str(current_user.id))

    # Проверить ключ — попробовать вызвать OpenAI
    ai_check = {"status": "unknown", "message": ""}
    try:
        import openai
        client = openai.OpenAI(api_key=data.value)
        # Тест: простой запрос
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        ai_check = {"status": "ok", "message": "OpenAI API работает. Ключ валиден."}
        logger.info("openai_key_validated")
    except Exception as e:
        err_msg = str(e)
        if "insufficient_quota" in err_msg or "billing" in err_msg:
            ai_check = {"status": "no_balance", "message": "Ключ валиден, но на счету недостаточно средств. Пополните баланс на platform.openai.com"}
        elif "invalid_api_key" in err_msg or "Incorrect API key" in err_msg:
            ai_check = {"status": "invalid", "message": "Неверный API ключ. Проверьте и попробуйте снова."}
        else:
            ai_check = {"status": "error", "message": f"Ошибка проверки: {err_msg[:200]}"}
        logger.warning("openai_key_check_failed", error=err_msg[:100])

    # Применить к ai-service (если ключ валиден)
    ai_result = {}
    if ai_check["status"] == "ok":
        try:
            async with httpx.AsyncClient(timeout=10) as http_client:
                resp = await http_client.post(
                    "http://localhost:8003/api/v1/ai/configure",
                    json={"openai_api_key": data.value, "openai_model": "gpt-4o"},
                )
                ai_result = resp.json()
        except Exception as e:
            ai_result = {"error": str(e)}

    return {
        "status": "saved",
        "key_set": True,
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


@router.on_event("startup")
async def load_settings_on_startup():
    """Загрузить OpenAI ключ из БД при старте core-api и отправить в ai-service."""
    pass  # Будет вызвано из main.py
