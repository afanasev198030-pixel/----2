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
        "openai_configured": current_settings.has_openai,
    }


@app.post("/api/v1/ai/configure")
async def configure_ai(data: dict):
    """Динамическая настройка OpenAI ключа и модели."""
    from app.config import get_settings
    import os
    
    api_key = data.get("openai_api_key", "")
    model = data.get("openai_model", "gpt-4o")
    
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        # Clear cached settings
        get_settings.cache_clear()
        
        # Reconfigure DSPy
        try:
            from app.services.dspy_modules import configure_dspy
            configure_dspy(api_key, model)
            logger.info("dspy_reconfigured", model=model)
        except Exception as e:
            logger.warning("dspy_reconfigure_failed", error=str(e))
        
        # Reinitialize indices
        try:
            from app.services.index_manager import get_index_manager
            idx = get_index_manager()
            idx._openai_api_key = api_key
            idx._openai_model = model
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
    
    new_settings = get_settings()
    return {
        "status": "configured",
        "openai_configured": new_settings.has_openai,
        "model": model,
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

    # Configure DSPy if OpenAI key available
    if settings.has_openai:
        try:
            from app.services.dspy_modules import configure_dspy
            configure_dspy(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
            logger.info("dspy_configured_on_startup")
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
