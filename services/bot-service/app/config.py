from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.get_logger()

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"
    
    # Core API
    CORE_API_URL: str = "http://core-api:8001"
    
    # File Service
    FILE_SERVICE_URL: str = "http://file-service:8002"
    
    # AI Service
    AI_SERVICE_URL: str = "http://ai-service:8003"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/1"
    
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()

# Fetch token from core-api if not set in env
import httpx
try:
    # Use internal docker network name for core-api if running in docker
    import os
    core_url = "http://core-api:8001" if os.environ.get("CORE_API_URL") else settings.CORE_API_URL
    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{core_url}/api/v1/settings/internal/telegram-config")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("bot_token"):
                settings.TELEGRAM_BOT_TOKEN = data["bot_token"]
except Exception as e:
    logger.warning("failed_to_fetch_telegram_config_from_core", error=str(e))
