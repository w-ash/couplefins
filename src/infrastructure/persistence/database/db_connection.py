import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from alembic import command
from src.config.settings import get_settings

# This module sits four levels below the repo root. Resolving the migration
# directory absolutely keeps `run_migrations` working from any cwd, not just a
# checkout root.
_ALEMBIC_DIR = Path(__file__).resolve().parents[4] / "alembic"

_engine_cache: list[AsyncEngine] = []
_session_factory_cache: list[async_sessionmaker[AsyncSession]] = []


def _get_engine() -> AsyncEngine:
    if not _engine_cache:
        settings = get_settings()
        connect_args = dict(settings.database.async_connect_args)
        kwargs: dict[str, object] = {
            "echo": settings.database.echo,
            "pool_pre_ping": True,
        }
        if settings.database.is_pooled_endpoint:
            kwargs["poolclass"] = NullPool
            connect_args["statement_cache_size"] = 0
        else:
            kwargs["pool_size"] = 3
            kwargs["max_overflow"] = 2
        kwargs["connect_args"] = connect_args
        _engine_cache.append(create_async_engine(settings.database.async_url, **kwargs))
    return _engine_cache[0]


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    if not _session_factory_cache:
        _session_factory_cache.append(
            async_sessionmaker(_get_engine(), expire_on_commit=False)
        )
    return _session_factory_cache[0]


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    factory = _get_session_factory()
    async with factory() as session:
        yield session


def run_migrations(sync_url: str) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    settings = get_settings()
    await asyncio.to_thread(run_migrations, settings.database.sync_url)


async def dispose_engine() -> None:
    if _engine_cache:
        await _engine_cache[0].dispose()
    reset_engine_cache()


def reset_engine_cache() -> None:
    _engine_cache.clear()
    _session_factory_cache.clear()
