import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.storage import ensure_bucket
from app.routes import router
from app.middleware.tracing import TracingMiddleware
from app.utils.logging import setup_logging



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


# Liveness
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "file-service"}


# Readiness — checks MinIO and Gotenberg
@app.get("/ready")
async def readiness_check():
    from fastapi.responses import JSONResponse
    checks = {}
    all_ok = True

    # MinIO
    try:
        from app.storage import minio_client
        minio_client.bucket_exists(settings.MINIO_BUCKET)
        checks["minio"] = {"status": "ok"}
    except Exception as e:
        checks["minio"] = {"status": "error", "detail": str(e)[:200]}
        all_ok = False

    # Gotenberg
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.GOTENBERG_URL}/health")
            if resp.status_code == 200:
                checks["gotenberg"] = {"status": "ok"}
            else:
                checks["gotenberg"] = {"status": "degraded", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        checks["gotenberg"] = {"status": "degraded", "detail": str(e)[:200]}

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "unavailable",
            "service": "file-service",
            "checks": checks,
        },
    )
