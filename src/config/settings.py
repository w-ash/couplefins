from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_cache: dict[str, Settings] = {}

_CACHE_KEY = "settings"


class LoggingConfig(BaseModel):
    output: Literal["json", "console"] = "console"
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://localhost:5432/couplefins"
    echo: bool = False

    @property
    def sync_url(self) -> str:
        return self.url.replace("+asyncpg", "+psycopg")

    @property
    def is_pooled_endpoint(self) -> bool:
        return "-pooler" in self.url

    @property
    def async_url(self) -> str:
        """URL with sslmode stripped — asyncpg uses the ssl connect_arg instead."""
        if "sslmode=" not in self.url:
            return self.url
        parsed = urlparse(self.url)
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    @property
    def async_connect_args(self) -> dict[str, object]:
        """Connect args for asyncpg, including ssl translated from sslmode."""
        args: dict[str, object] = {}
        if "sslmode=" in self.url:
            args["ssl"] = "require"
        return args


# HS256 signing keys must be >=32 bytes (RFC 7518 §3.2 / PyJWT InsecureKeyLength).
_MIN_JWT_SECRET_BYTES = 32


class AuthConfig(BaseModel):
    jwt_secret: str = "couplefins-dev-secret-change-in-prod"  # noqa: S105
    token_expiry_minutes: int = 60 * 24 * 7  # 7 days
    cookie_name: str = "couplefins_session"
    cookie_secure: bool = False  # True in prod (HTTPS)
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @field_validator("jwt_secret")
    @classmethod
    def _min_secret_bytes(cls, v: str) -> str:
        # Reject a short secret at startup instead of leaking a runtime
        # InsecureKeyLengthWarning on every token sign. Count bytes, not code
        # points.
        if len(v.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"jwt_secret must be at least {_MIN_JWT_SECRET_BYTES} bytes for HS256"
            )
        return v


class ChatConfig(BaseModel):
    anthropic_api_key: str | None = None
    model_id: str = "claude-sonnet-4-6"
    max_turns: int = 8


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    chat: ChatConfig = ChatConfig()
    cors_origins: list[str] = ["http://localhost:5174"]


def get_settings() -> Settings:
    if _CACHE_KEY not in _cache:
        _cache[_CACHE_KEY] = Settings()
    return _cache[_CACHE_KEY]


def reset_settings() -> None:
    _cache.clear()
