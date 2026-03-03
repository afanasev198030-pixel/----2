import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.storage import ensure_bucket
from app.routes import router
from app.middleware.tracing import TracingMiddleware


def setup_logging():
    """Configure structlog for JSON logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    setup_logging()
    logger = structlog.get_logger()
    logger.info("service_starting", service=settings.SERVICE_NAME)
    
    try:
        ensure_bucket()
        logger.info("service_ready", service=settings.SERVICE_NAME)
    except Exception as e:
        logger.error("service_startup_failed", service=settings.SERVICE_NAME, error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("service_shutting_down", service=settings.SERVICE_NAME)


app = FastAPI(
    title="File Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TracingMiddleware, service_name=settings.SERVICE_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "file-service",
    }
