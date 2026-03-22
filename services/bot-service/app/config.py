from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"
    CORE_API_URL: str = "http://core-api:8001"
    FILE_SERVICE_URL: str = "http://file-service:8002"
    AI_SERVICE_URL: str = "http://ai-service:8003"
    REDIS_URL: str = "redis://redis:6379/1"
    SERVICE_NAME: str = "bot-service"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()


def fetch_telegram_config() -> None:
    """Fetch bot token from core-api if not set via env."""
    import httpx
    import structlog

    logger = structlog.get_logger()
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{settings.CORE_API_URL}/api/v1/settings/internal/telegram-config")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("bot_token"):
                    settings.TELEGRAM_BOT_TOKEN = data["bot_token"]
                    logger.info("telegram_config_loaded_from_core")
    except Exception as e:
        logger.warning("failed_to_fetch_telegram_config_from_core", error=str(e))
