from pydantic import BaseModel
from pydantic_settings import BaseSettings

_cache: dict[str, Settings] = {}

_CACHE_KEY = "settings"


class DatabaseConfig(BaseModel):
    url: str = "sqlite+aiosqlite:///data/couplefins.db"
    echo: bool = False


class Settings(BaseSettings):
    model_config = {"env_nested_delimiter": "__"}

    database: DatabaseConfig = DatabaseConfig()
    cors_origins: list[str] = ["http://localhost:5174"]


def get_settings() -> Settings:
    if _CACHE_KEY not in _cache:
        _cache[_CACHE_KEY] = Settings()
    return _cache[_CACHE_KEY]


def reset_settings() -> None:
    _cache.clear()
