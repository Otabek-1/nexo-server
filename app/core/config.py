from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "Nexo API"
    api_prefix: str = "/api/v1"
    debug: bool = True
    cors_allow_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "nexo"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "disable"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = Field(default="change-me-access", min_length=16)
    jwt_refresh_secret_key: str = Field(default="change-me-refresh", min_length=16)
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    storage_provider: Literal["local", "minio", "supabase"] = "local"
    storage_local_dir: str = "./storage"
    storage_sign_ttl_seconds: int = 900
    storage_max_file_size: int = 10 * 1024 * 1024
    storage_allowed_mime: str = (
        "image/png,image/jpeg,image/jpg,image/webp,image/gif,image/svg+xml,video/mp4"
    )

    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "nexo"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_base_url: str = ""

    sentry_dsn: str = ""

    telegram_bot_token: str = ""
    telegram_bot_username: str = "nexo_bot"
    telegram_webhook_secret: str = ""

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            if self.database_url.startswith("postgresql+asyncpg://"):
                return self.database_url
            if self.database_url.startswith("postgresql://"):
                return "postgresql+asyncpg://" + self.database_url.removeprefix("postgresql://")
            return self.database_url
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        ssl_query = ""
        if self.db_sslmode == "require":
            ssl_query = "?ssl=require"
        return (
            f"postgresql+asyncpg://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
            f"{ssl_query}"
        )

    @property
    def sync_database_url(self) -> str:
        url = self.async_database_url
        if url.startswith("postgresql+asyncpg://"):
            converted = "postgresql+psycopg2://" + url.removeprefix("postgresql+asyncpg://")
        else:
            converted = url
        return converted.replace("ssl=require", "sslmode=require")


@lru_cache
def get_settings() -> Settings:
    return Settings()
