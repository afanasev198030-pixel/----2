"""
Unified LLM client factory.
Supports DeepSeek, OpenAI, and custom OpenAI-compatible providers.
All use the same openai Python SDK — just different base_url.
"""
import openai
import structlog

logger = structlog.get_logger()


def get_llm_client(api_key: str = None, base_url: str = None) -> openai.OpenAI:
    """Create OpenAI-compatible client for any provider (DeepSeek, OpenAI, etc.)."""
    from app.config import get_settings
    settings = get_settings()

    key = api_key or settings.effective_api_key
    url = base_url or settings.effective_base_url

    if not key:
        raise ValueError("No LLM API key configured. Set LLM_API_KEY or OPENAI_API_KEY.")

    client = openai.OpenAI(api_key=key, base_url=url)
    logger.debug("llm_client_created", provider=settings.LLM_PROVIDER, base_url=url)
    return client


def get_model() -> str:
    """Return the effective chat model name."""
    from app.config import get_settings
    return get_settings().effective_model


def get_reasoning_model() -> str:
    """Return the reasoning model (DeepSeek R1) or fallback to chat model."""
    from app.config import get_settings
    s = get_settings()
    return s.LLM_REASONING_MODEL or s.effective_model
