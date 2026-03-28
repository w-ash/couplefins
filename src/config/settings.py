from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

_cache: dict[str, Settings] = {}

_CACHE_KEY = "settings"


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://localhost:5432/couplefins"
    echo: bool = False

    @property
    def sync_url(self) -> str:
        return self.url.replace("+asyncpg", "+psycopg")


class AuthConfig(BaseModel):
    jwt_secret: str = "couplefins-dev-secret-change-in-prod"  # noqa: S105
    token_expiry_minutes: int = 60 * 24 * 7  # 7 days
    cookie_name: str = "couplefins_session"
    cookie_secure: bool = False  # True in prod (HTTPS)
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    cors_origins: list[str] = ["http://localhost:5174"]


def get_settings() -> Settings:
    if _CACHE_KEY not in _cache:
        _cache[_CACHE_KEY] = Settings()
    return _cache[_CACHE_KEY]


def reset_settings() -> None:
    _cache.clear()
