from pydantic_settings import BaseSettings
from functools import lru_cache
import structlog

logger = structlog.get_logger()


class Settings(BaseSettings):
    CORE_API_URL: str = "http://core-api:8001"
    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
