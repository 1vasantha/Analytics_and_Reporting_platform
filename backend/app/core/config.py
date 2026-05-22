# Application configuration.

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Application settings loaded from environment variables
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    PROJECT_NAME: str = "Analytics Platform"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Security
    SECRET_KEY: str = Field(
        default="change-me-in-production-this-must-be-at-least-32-chars",
        min_length=32,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Parse the comma-separated CORS origins string into a list
    @property
    def cors_origins_list(self) -> list[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        if self.BACKEND_CORS_ORIGINS.startswith("["):
            import json
            return json.loads(self.BACKEND_CORS_ORIGINS)
        return [s.strip() for s in self.BACKEND_CORS_ORIGINS.split(",") if s.strip()]

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "analytics"
    POSTGRES_PASSWORD: str = "analytics"
    POSTGRES_DB: str = "analytics"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # Database URL
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Sync URL used by Alembic migrations
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # Redis URL
    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_TIME_LIMIT: int = 300
    CELERY_TASK_SOFT_TIME_LIMIT: int = 240

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or f"{self.REDIS_URL.rsplit('/', 1)[0]}/1"

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or f"{self.REDIS_URL.rsplit('/', 1)[0]}/2"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_INGESTION_PER_MINUTE: int = 1000
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@analytics.local"
    SMTP_FROM_NAME: str = "Analytics Platform"
    SMTP_TLS: bool = False

    # Ingestion
    MAX_BATCH_SIZE: int = 1000
    MAX_CSV_SIZE_MB: int = 50
    INGESTION_BUFFER_SECONDS: int = 5

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

# Cached settings instance — instantiated once per process
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()