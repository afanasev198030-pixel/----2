import logging
import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.stdlib import LoggerFactory

from app.config import settings


def setup_logging() -> None:
    """Configure structlog with JSON formatting."""
    # Map log level string to logging level
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
            add_log_level,
            TimeStamper(fmt="iso"),
            JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Bind service_name from settings to structlog context
    structlog.contextvars.bind_contextvars(service_name=settings.SERVICE_NAME)
