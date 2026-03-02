from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.routers import parser, classifier, risk
from app.routers import smart_parser

logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(
    title="AI Service",
    version="0.2.0",
    description="AI Service: OCR parsing, HS classification (RAG), risk assessment, multi-agent pipeline",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routers (regex fallback)
app.include_router(parser.router)
app.include_router(classifier.router)
app.include_router(risk.router)

# New RAG/LLM router
app.include_router(smart_parser.router)


@app.get("/health")
async def health():
    from app.services.index_manager import get_index_manager
    from app.config import get_settings
    current_settings = get_settings()
    idx = get_index_manager()
    return {
        "status": "ok",
        "service": current_settings.SERVICE_NAME,
        "rag_available": idx.available,
        "chromadb_connected": idx.chromadb_connected,
        "openai_configured": current_settings.has_llm,  # backward compat key name
        "llm_configured": current_settings.has_llm,
        "llm_provider": current_settings.LLM_PROVIDER,
        "llm_model": current_settings.effective_model,
        "embed_provider": current_settings.EMBED_PROVIDER,
    }


# Хранилище последнего парсинга (in-memory)
_last_parse: dict = {}


@app.get("/api/v1/ai/health-detailed")
async def health_detailed():
    """Расширенный health с DSPy, RAG counts, last parse — для дебаг-панели."""
    from app.services.index_manager import get_index_manager, get_training_log
    from app.config import get_settings
    current_settings = get_settings()
    idx = get_index_manager()

    # DSPy status
    dspy_info = {"available": False, "configured": False, "demos_count": 0}
    try:
        from app.services.dspy_modules import _dspy_available, HSCodeClassifier
        dspy_info["available"] = _dspy_available
        if _dspy_available:
            import dspy
            dspy_info["configured"] = dspy.settings.lm is not None
        dspy_info["demos_count"] = len(HSCodeClassifier._HS_DEMOS or [])
    except Exception:
        pass

    # RAG collection counts
    rag_counts = {"hs_codes": 0, "risk_rules": 0, "precedents": 0}
    try:
        if idx._chroma_client:
            for name in rag_counts:
                try:
                    col = idx._chroma_client.get_or_create_collection(name)
                    rag_counts[name] = col.count()
                except Exception:
                    pass
    except Exception:
        pass

    # HS classification log
    hs_log = []
    try:
        from app.services.dspy_modules import get_hs_classify_log
        hs_log = get_hs_classify_log()[-20:]
    except Exception:
        pass

    return {
        "status": "ok",
        "service": current_settings.SERVICE_NAME,
        "llm_configured": current_settings.has_llm,
        "llm_provider": current_settings.LLM_PROVIDER,
        "llm_model": current_settings.effective_model,
        "embed_provider": current_settings.EMBED_PROVIDER,
        "dspy": dspy_info,
        "rag": rag_counts,
        "last_parse": _last_parse,
        "hs_classify_log": hs_log,
        "training_log": get_training_log()[-30:],
    }


@app.post("/api/v1/ai/configure")
async def configure_ai(data: dict):
    """Динамическая настройка LLM ключа, модели, провайдера. Обратная совместимость с openai_api_key."""
    from app.config import get_settings
    import os

    # Accept both new and legacy keys
    api_key = data.get("api_key") or data.get("openai_api_key", "")
    model = data.get("model") or data.get("openai_model", "")
    base_url = data.get("base_url", "")
    provider = (data.get("provider") or os.environ.get("LLM_PROVIDER", "deepseek")).lower()

    # Не отправлять gpt-4o в DeepSeek — подставить deepseek-chat
    if provider == "deepseek" and (not model or model.startswith("gpt-")):
        model = "deepseek-chat"
    if not model:
        model = "deepseek-chat" if provider == "deepseek" else "gpt-4o"
    if not base_url:
        base_url = "https://api.deepseek.com" if provider == "deepseek" else "https://api.openai.com/v1"

    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        os.environ["OPENAI_API_KEY"] = api_key  # backward compat
    if model:
        os.environ["LLM_MODEL"] = model
        os.environ["OPENAI_MODEL"] = model  # backward compat
    if base_url:
        os.environ["LLM_BASE_URL"] = base_url
    if provider:
        os.environ["LLM_PROVIDER"] = provider

    # Clear cached settings so new env vars take effect
    get_settings.cache_clear()
    new_settings = get_settings()

    if api_key:
        # Reconfigure DSPy
        try:
            from app.services.dspy_modules import configure_dspy
            configure_dspy(api_key=api_key, model=new_settings.effective_model, base_url=new_settings.effective_base_url)
            logger.info("dspy_reconfigured", model=new_settings.effective_model, provider=new_settings.LLM_PROVIDER)
        except Exception as e:
            logger.warning("dspy_reconfigure_failed", error=str(e))

        # Reinitialize indices
        try:
            from app.services.index_manager import get_index_manager
            idx = get_index_manager()
            idx._openai_api_key = api_key
            idx._openai_model = new_settings.effective_model
            import json
            from pathlib import Path
            rules_path = Path(__file__).parent / "rules" / "risk_rules.json"
            risk_rules = []
            if rules_path.exists():
                with open(rules_path) as f:
                    risk_rules = json.load(f)
            idx.init_indices(risk_rules=risk_rules)
            logger.info("index_manager_reconfigured")
        except Exception as e:
            logger.warning("index_manager_reconfigure_failed", error=str(e))

    return {
        "status": "configured",
        "openai_configured": new_settings.has_llm,  # backward compat
        "llm_configured": new_settings.has_llm,
        "provider": new_settings.LLM_PROVIDER,
        "model": new_settings.effective_model,
        "base_url": new_settings.effective_base_url,
    }


@app.get("/api/v1/ai/models")
async def list_llm_models():
    """
    Получить список моделей из текущего LLM провайдера (OpenAI-совместимый / proxy).
    Использует настройки ключа и base_url из ai-service.
    """
    from app.config import get_settings
    import openai

    current_settings = get_settings()
    if not current_settings.has_llm:
        return {"models": [], "error": "LLM API ключ не настроен"}

    client = openai.OpenAI(
        api_key=current_settings.effective_api_key,
        base_url=current_settings.effective_base_url,
    )

    try:
        resp = client.models.list()
        items = []
        for m in resp.data:
            items.append(
                {
                    "id": getattr(m, "id", ""),
                    "created": getattr(m, "created", None),
                    "owned_by": getattr(m, "owned_by", ""),
                }
            )
        return {"models": items}
    except Exception as e:
        logger.error("llm_models_list_failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"Не удалось получить список моделей: {str(e)[:200]}")


@app.on_event("startup")
async def startup_event():
    logger.info("ai_service_started", service=settings.SERVICE_NAME)

    # Init observability (Arize-Phoenix)
    try:
        from app.services.observability import init_observability
        init_observability(settings.PHOENIX_HOST, settings.PHOENIX_PORT)
    except Exception as e:
        logger.warning("observability_init_failed", error=str(e))

    # Fetch LLM key from core-api DB (persisted settings survive restarts)
    try:
        import httpx, os
        resp = httpx.get(f"{settings.CORE_API_URL}/api/v1/settings/internal/llm-config", timeout=10)
        if resp.status_code == 200:
            db_settings = resp.json()
            db_key = db_settings.get("llm_api_key", "")
            db_provider = db_settings.get("llm_provider", "")
            db_base_url = db_settings.get("llm_base_url", "")
            db_model = db_settings.get("openai_model", "")
            if db_key and db_key != "sk-your-key-here":
                os.environ["LLM_API_KEY"] = db_key
                os.environ["OPENAI_API_KEY"] = db_key
                if db_provider:
                    os.environ["LLM_PROVIDER"] = db_provider
                if db_base_url:
                    os.environ["LLM_BASE_URL"] = db_base_url
                if db_model:
                    os.environ["LLM_MODEL"] = db_model
                    os.environ["OPENAI_MODEL"] = db_model
                get_settings.cache_clear()
                logger.info("llm_key_loaded_from_db", provider=db_provider, model=db_model,
                            base_url=db_base_url[:30] if db_base_url else "", key_prefix=db_key[:8] + "...")
            else:
                logger.info("no_llm_key_in_db")
        else:
            logger.warning("db_settings_fetch_non_200", status=resp.status_code)
    except Exception as e:
        logger.warning("db_settings_fetch_failed", error=str(e)[:100])

    # Reload settings after DB fetch
    from app.config import get_settings as _gs
    current = _gs()

    # Configure DSPy if LLM key available
    if current.has_llm:
        try:
            from app.services.dspy_modules import configure_dspy
            configure_dspy(
                api_key=current.effective_api_key,
                model=current.effective_model,
                base_url=current.effective_base_url,
            )
            logger.info("dspy_configured_on_startup", provider=current.LLM_PROVIDER, model=current.effective_model)

            # Load optimized HS classifier if exists
            from pathlib import Path
            opt_path = Path(__file__).parent / "ml_models" / "hs_classifier_optimized.json"
            if opt_path.exists():
                try:
                    from app.services.dspy_modules import HSCodeSignature
                    import dspy
                    optimized = dspy.Predict(HSCodeSignature)
                    optimized.load(str(opt_path))
                    logger.info("hs_classifier_optimized_loaded", path=str(opt_path))
                except Exception as oe:
                    logger.warning("hs_classifier_optimized_load_failed", error=str(oe)[:100])
        except Exception as e:
            logger.warning("dspy_startup_config_failed", error=str(e))

    # Initialize LlamaIndex indices (non-blocking)
    try:
        from app.services.index_manager import get_index_manager
        idx = get_index_manager()
        # Load risk rules from JSON
        import json
        from pathlib import Path
        rules_path = Path(__file__).parent / "rules" / "risk_rules.json"
        risk_rules = []
        if rules_path.exists():
            with open(rules_path) as f:
                risk_rules = json.load(f)

        idx.init_indices(risk_rules=risk_rules)
        logger.info("index_manager_initialized_on_startup")
    except Exception as e:
        logger.warning("index_manager_startup_failed", error=str(e))
