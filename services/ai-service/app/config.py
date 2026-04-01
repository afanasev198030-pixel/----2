from pydantic_settings import BaseSettings
from functools import lru_cache

# logging will be configured in utils/logging.py
# we keep import only where needed to avoid circular imports


class Settings(BaseSettings):
    # Core API
    CORE_API_URL: str = "http://core-api:8001"

    # Calc service (exchange rates, payments)
    CALC_SERVICE_URL: str = "http://calc-service:8005"

    # Service
    SERVICE_NAME: str = "ai-service"
    LOG_LEVEL: str = "INFO"

    # LLM Provider settings
    LLM_PROVIDER: str = "deepseek"  # deepseek, openai, cloud_ru, anthropic, custom
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""  # Primary API key
    LLM_MODEL: str = "deepseek-chat"
    LLM_REASONING_MODEL: str = "deepseek-reasoner"
    LLM_PROJECT_ID: str = ""  # Cloud.ru x-project-id header (optional)

    # Anthropic (Claude Opus 4.6)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-opus-4-6-202503"
    EMBED_PROVIDER: str = "cloud_ru"  # cloud_ru, openai, local
    EMBED_MODEL: str = "BAAI/bge-m3"  # Cloud.ru: BAAI/bge-m3 (1024 dim, multilingual)
    EMBED_BASE_URL: str = "https://foundation-models.api.cloud.ru/v1"
    EMBED_API_KEY: str = ""  # empty = use effective_api_key

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

    # Parallel file processing in parse-smart
    PARSE_PARALLEL_WORKERS: int = 2

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
        if self.LLM_PROVIDER == "anthropic":
            return self.ANTHROPIC_API_KEY or self.LLM_API_KEY or self.OPENAI_API_KEY or ""
        return self.LLM_API_KEY or self.OPENAI_API_KEY or ""

    @property
    def effective_embed_api_key(self) -> str:
        """Return API key for embeddings (falls back to LLM key)."""
        return self.EMBED_API_KEY or self.effective_api_key

    @property
    def effective_embed_base_url(self) -> str:
        """Return base URL for embeddings (falls back to LLM base URL)."""
        return self.EMBED_BASE_URL or self.effective_base_url

    @property
    def effective_base_url(self) -> str:
        """Return the base URL for the configured provider (profile-driven)."""
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        from app.services.llm_client import get_provider_profile
        return get_provider_profile(self.LLM_PROVIDER)["base_url"]

    @property
    def effective_model(self) -> str:
        """Return the best available model name (profile-driven)."""
        if self.LLM_MODEL:
            return self.LLM_MODEL
        if self.OPENAI_MODEL:
            return self.OPENAI_MODEL
        from app.services.llm_client import get_provider_profile
        return get_provider_profile(self.LLM_PROVIDER)["default_model"]

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance.

    Note: setup_logging() should be called *before* first get_settings()
    to ensure proper context binding.
    """
    return Settings()
