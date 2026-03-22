from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.routers import payments
from app.middleware.tracing import TracingMiddleware
from app.utils.logging import setup_logging

# Setup structured logging first
setup_logging()
logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(title="Calc Service", version="0.1.0")

app.add_middleware(TracingMiddleware, service_name=settings.SERVICE_NAME)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(payments.router)


# Liveness
@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


# Readiness (no critical external deps — autonomous service)
@app.get("/ready")
async def readiness():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.on_event("startup")
async def startup():
    logger.info("calc_service_started", service=settings.SERVICE_NAME)
