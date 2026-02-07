from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.config import settings
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.logging import setup_logging
from app.routers import (
    auth,
    declarations,
    declaration_items,
    workflow,
    documents,
    classifiers,
    users,
)

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
    """Setup logging and log service start."""
    setup_logging()
    logger.info(
        "service_started",
        service_name=settings.SERVICE_NAME,
        version="0.1.0",
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "core-api",
    }


# Include routers
app.include_router(auth.router)
app.include_router(declarations.router)
app.include_router(declaration_items.router)
app.include_router(workflow.router)
app.include_router(documents.router)
app.include_router(classifiers.router)
app.include_router(users.router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
