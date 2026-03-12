from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # Service settings
    SERVICE_NAME: str = "core-api"
    LOG_LEVEL: str = "INFO"

    # EEC portal classifier sync
    EEC_PORTAL_BASE_URL: str = "https://portal.eaeunion.org/sites/odata/_api/web/lists"
    EEC_SYNC_ENABLED: bool = True
    EEC_SYNC_INTERVAL_HOURS: int = 24

    # AI training sync
    AI_SERVICE_URL: str = "http://ai-service:8003"
    AI_TRAINING_SYNC_ENABLED: bool = True
    AI_TRAINING_SYNC_INTERVAL_HOURS: int = 24
    AI_TRAINING_SYNC_DECL_LIMIT: int = 200

    # Telegram
    TELEGRAM_BOT_USERNAME: str = "DigitalBrokerBot"

    @property
    def database_url(self) -> str:
        """Returns async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
