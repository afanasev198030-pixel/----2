import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog

from app.config import settings

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging with correlation_id."""

    async def dispatch(self, request: Request, call_next):
        # Generate or read correlation_id from X-Request-ID header
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Bind correlation_id and service_name to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            service_name=settings.SERVICE_NAME,
        )
        
        # Log request start
        start_time = time.time()
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
            service_name=settings.SERVICE_NAME,
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                correlation_id=correlation_id,
                service_name=settings.SERVICE_NAME,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise
        
        # Log request end
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            correlation_id=correlation_id,
            service_name=settings.SERVICE_NAME,
            duration_ms=round(duration_ms, 2),
        )
        
        # Add correlation_id to response headers
        response.headers["X-Request-ID"] = correlation_id
        
        return response
