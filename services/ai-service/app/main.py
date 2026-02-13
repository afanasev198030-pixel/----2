from fastapi import FastAPI
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


@app.post("/api/v1/ai/configure")
async def configure_ai(data: dict):
    """Динамическая настройка LLM ключа, модели, провайдера. Обратная совместимость с openai_api_key."""
    from app.config import get_settings
    import os

    # Accept both new and legacy keys
    api_key = data.get("api_key") or data.get("openai_api_key", "")
    model = data.get("model") or data.get("openai_model", "")
    base_url = data.get("base_url", "")
    provider = data.get("provider", "")

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


@app.on_event("startup")
async def startup_event():
    logger.info("ai_service_started", service=settings.SERVICE_NAME)

    # Init observability (Arize-Phoenix)
    try:
        from app.services.observability import init_observability
        init_observability(settings.PHOENIX_HOST, settings.PHOENIX_PORT)
    except Exception as e:
        logger.warning("observability_init_failed", error=str(e))

    # Configure DSPy if LLM key available
    if settings.has_llm:
        try:
            from app.services.dspy_modules import configure_dspy
            configure_dspy(
                api_key=settings.effective_api_key,
                model=settings.effective_model,
                base_url=settings.effective_base_url,
            )
            logger.info("dspy_configured_on_startup", provider=settings.LLM_PROVIDER, model=settings.effective_model)
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
