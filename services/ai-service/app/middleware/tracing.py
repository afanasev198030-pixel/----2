import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


logger = structlog.get_logger()


class TracingMiddleware(BaseHTTPMiddleware):
    """Propagate X-Request-ID across services and log requests."""

    def __init__(self, app, service_name: str = "unknown"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            service_name=self.service_name,
        )

        start_time = time.time()
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = correlation_id
        return response


def get_correlation_id() -> str:
    """Retrieve current correlation_id from structlog context."""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("correlation_id", "")


def tracing_headers() -> dict[str, str]:
    """Build headers dict with X-Request-ID for outbound httpx calls."""
    cid = get_correlation_id()
    return {"X-Request-ID": cid} if cid else {}
