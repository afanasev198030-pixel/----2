from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False
    GOTENBERG_URL: str = "http://gotenberg:3000"
    SERVICE_NAME: str = "file-service"
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
