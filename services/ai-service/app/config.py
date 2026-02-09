from pydantic_settings import BaseSettings
from functools import lru_cache
import structlog

logger = structlog.get_logger()


class Settings(BaseSettings):
    # Core API
    CORE_API_URL: str = "http://core-api:8001"

    # Service
    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ChromaDB
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

    # Phoenix observability
    PHOENIX_HOST: str = "phoenix"
    PHOENIX_PORT: int = 6006

    @property
    def chromadb_url(self) -> str:
        return f"http://{self.CHROMADB_HOST}:{self.CHROMADB_PORT}"

    @property
    def has_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY != "sk-your-key-here")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
