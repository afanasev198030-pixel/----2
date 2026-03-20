from pydantic_settings import BaseSettings
from functools import lru_cache
import structlog

logger = structlog.get_logger()


class Settings(BaseSettings):
    # Core API
    CORE_API_URL: str = "http://core-api:8001"

    # Calc service (exchange rates, payments)
    CALC_SERVICE_URL: str = "http://calc-service:8005"

    # Service
    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    # LLM Provider settings (DeepSeek as default, OpenAI/Cloud.ru as alternatives)
    LLM_PROVIDER: str = "deepseek"  # deepseek, openai, cloud_ru, custom
    LLM_BASE_URL: str = "https://api.deepseek.com"  # DeepSeek API endpoint
    LLM_API_KEY: str = ""  # Primary API key
    LLM_MODEL: str = "deepseek-chat"  # Default: DeepSeek V3
    LLM_REASONING_MODEL: str = "deepseek-reasoner"  # DeepSeek R1 for complex tasks
    LLM_PROJECT_ID: str = ""  # Cloud.ru x-project-id header (optional)
    EMBED_PROVIDER: str = "local"  # local (onnxruntime), openai

    # Vision OCR (DeepSeek-OCR-2 via Cloud.ru — replaces Tesseract/pdfplumber)
    OCR_ENABLED: bool = False
    OCR_BASE_URL: str = "https://foundation-models.api.cloud.ru/v1"
    OCR_API_KEY: str = ""
    OCR_MODEL: str = "deepseek-ai/DeepSeek-OCR-2"
    OCR_PROJECT_ID: str = ""
    OCR_TIMEOUT: int = 120

    # Legacy OpenAI (backward compatibility)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ChromaDB
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

    # Phoenix observability
    PHOENIX_HOST: str = "phoenix"
    PHOENIX_PORT: int = 6006

    # Task Queue (ARQ + Redis) - for async AI processing to prevent OOM
    REDIS_BROKER_URL: str = "redis://redis:6379/2"
    TASK_QUEUE_ENABLED: bool = True
    ARQ_QUEUE_NAME: str = "ai_tasks"
    ARQ_MAX_JOBS: int = 3
    ARQ_JOB_TIMEOUT_SECONDS: int = 1800  # 30 minutes

    @property
    def chromadb_url(self) -> str:
        return f"http://{self.CHROMADB_HOST}:{self.CHROMADB_PORT}"

    @property
    def has_vision_ocr(self) -> bool:
        """Check if Vision OCR is configured and enabled."""
        return bool(self.OCR_ENABLED and self.OCR_API_KEY)

    @property
    def has_llm(self) -> bool:
        """Check if any LLM API key is configured."""
        key = self.LLM_API_KEY or self.OPENAI_API_KEY
        return bool(key and key != "sk-your-key-here")

    @property
    def has_openai(self) -> bool:
        """Backward compatibility."""
        return self.has_llm

    @property
    def effective_api_key(self) -> str:
        """Return the best available API key."""
        return self.LLM_API_KEY or self.OPENAI_API_KEY or ""

    @property
    def effective_base_url(self) -> str:
        """Return the base URL for the configured provider."""
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        if self.LLM_PROVIDER == "openai":
            return "https://api.openai.com/v1"
        if self.LLM_PROVIDER == "cloud_ru":
            return "https://foundation-models.api.cloud.ru/v1"
        return "https://api.deepseek.com"

    @property
    def effective_model(self) -> str:
        """Return the best available model name."""
        return self.LLM_MODEL or self.OPENAI_MODEL or "deepseek-chat"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
