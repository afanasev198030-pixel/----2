import logging
import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level

from app.config import get_settings


def setup_logging() -> None:
    """Configure structlog with JSON formatting.

    Standard template used across all services.
    Supports contextvars for correlation_id and service_name.
    """
    settings = get_settings()

    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level = log_level_map.get(settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_log_level,
            TimeStamper(fmt="iso"),
            JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind default context
    structlog.contextvars.bind_contextvars(
        service_name=settings.SERVICE_NAME,
    )
