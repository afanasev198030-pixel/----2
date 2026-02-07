from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.routers import parser, classifier, risk

logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(
    title="AI Service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parser.router)
app.include_router(classifier.router)
app.include_router(risk.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.on_event("startup")
async def startup_event():
    logger.info("ai_service_started", service=settings.SERVICE_NAME)
