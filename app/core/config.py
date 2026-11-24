from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, model_validator
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
    debug: bool = False
    cors_allow_origins: str = (
        "http://localhost:5173,http://localhost:3000,https://nexoo.space,https://www.nexoo.space"
    )

    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "nexo"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "disable"
    jwt_secret_key: str = ""
    jwt_refresh_secret_key: str = ""
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    storage_provider: Literal["local", "minio", "supabase", "s3"] = "local"
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

    @model_validator(mode="after")
    def validate_secrets(self):
        weak_secrets = {
            "",
            "change-me-access",
            "change-me-refresh",
        }
        for name in ("jwt_secret_key", "jwt_refresh_secret_key"):
            value = getattr(self, name)
            if (
                value in weak_secrets
                or value.startswith("replace-with")
                or len(value) < 32
            ):
                raise ValueError(f"{name.upper()} must be at least 32 characters and must not use a placeholder")
        if self.app_env == "prod" and self.debug:
            raise ValueError("DEBUG must be false when APP_ENV=prod")
        return self

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

@lru_cache
def get_settings() -> Settings:
    return Settings()
