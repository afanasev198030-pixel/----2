"""
Unified LLM client factory.
Supports DeepSeek, OpenAI, Cloud.ru and any OpenAI-compatible provider.
All use the same openai Python SDK — just different base_url.

Provider capabilities are declared in PROVIDER_PROFILES — adding a new
provider is a single dict entry, no code changes in parsers needed.
"""
import openai
import structlog

from app.services.usage_tracker import TrackedOpenAIClient

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Provider profiles — single source of truth for provider capabilities.
# To add a new provider: add an entry here. All parsers adapt automatically.
# ---------------------------------------------------------------------------
PROVIDER_PROFILES: dict[str, dict] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "reasoning_model": "deepseek-reasoner",
        "supports_json_mode": True,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "reasoning_model": "gpt-4o",
        "supports_json_mode": True,
    },
    "cloud_ru": {
        "base_url": "https://foundation-models.api.cloud.ru/v1",
        "default_model": "openai/gpt-oss-120b",
        "reasoning_model": "openai/gpt-oss-120b",
        "supports_json_mode": True,
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "reasoning_model": "claude-3-5-sonnet-20241022",
        "supports_json_mode": False,
    },
    "proxyapi": {
        "base_url": "https://openai.api.proxyapi.ru/v1",
        "default_model": "anthropic/claude-opus-4-6",
        "reasoning_model": "anthropic/claude-opus-4-6",
        "supports_json_mode": True,
    },
}

_DEFAULT_PROFILE: dict = {
    "base_url": "https://api.openai.com/v1",
    "default_model": "gpt-4o",
    "reasoning_model": "gpt-4o",
    "supports_json_mode": True,
}


def get_provider_profile(provider: str | None = None) -> dict:
    """Return capabilities profile for the given (or current) provider."""
    if provider is None:
        from app.config import get_settings
        provider = get_settings().LLM_PROVIDER
    return PROVIDER_PROFILES.get(provider.lower(), _DEFAULT_PROFILE)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def get_llm_client(
    api_key: str = None,
    base_url: str = None,
    operation: str = "chat",
    declaration_id: str = "",
    company_id: str = "",
):
    """Create tracked OpenAI-compatible client for any provider."""
    from app.config import get_settings

    settings = get_settings()

    key = api_key or settings.effective_api_key
    url = base_url or settings.effective_base_url

    if not key:
        raise ValueError("No LLM API key configured. Set LLM_API_KEY or OPENAI_API_KEY.")

    extra_headers = {}
    if settings.LLM_PROJECT_ID:
        extra_headers["x-project-id"] = settings.LLM_PROJECT_ID

    raw_client = openai.OpenAI(
        api_key=key,
        base_url=url,
        default_headers=extra_headers or None,
    )
    logger.debug("llm_client_created", provider=settings.LLM_PROVIDER, base_url=url, operation=operation)
    return TrackedOpenAIClient(
        raw_client,
        operation=operation,
        declaration_id=declaration_id,
        company_id=company_id,
    )


def get_model() -> str:
    """Return the effective chat model name."""
    from app.config import get_settings
    return get_settings().effective_model


def get_reasoning_model() -> str:
    """Return the reasoning model or fallback to chat model."""
    from app.config import get_settings
    s = get_settings()
    return s.LLM_REASONING_MODEL or s.effective_model


# ---------------------------------------------------------------------------
# Capability helpers — all parsers use these instead of hardcoding
# ---------------------------------------------------------------------------

def supports_json_mode() -> bool:
    """Check if current LLM provider supports response_format=json_object.
    ProxyAPI with Claude models doesn't support json mode."""
    profile = get_provider_profile()
    if not profile["supports_json_mode"]:
        return False
    from app.config import get_settings
    model = get_settings().effective_model.lower()
    if "claude" in model or "anthropic" in model:
        return False
    return True


def json_format_kwargs() -> dict:
    """Return response_format kwarg for providers that support it, empty dict otherwise.

    Usage: client.chat.completions.create(..., **json_format_kwargs())
    """
    if supports_json_mode():
        return {"response_format": {"type": "json_object"}}
    return {}
