import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from src.config.settings import get_settings

_engine_cache: list[AsyncEngine] = []
_session_factory_cache: list[async_sessionmaker[AsyncSession]] = []


def _get_engine() -> AsyncEngine:
    if not _engine_cache:
        settings = get_settings()
        _engine_cache.append(
            create_async_engine(
                settings.database.url,
                echo=settings.database.echo,
                pool_pre_ping=True,
            )
        )
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


def _run_migrations(sync_url: str) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    settings = get_settings()
    await asyncio.to_thread(_run_migrations, settings.database.sync_url)


async def dispose_engine() -> None:
    if _engine_cache:
        await _engine_cache[0].dispose()
    reset_engine_cache()


def reset_engine_cache() -> None:
    _engine_cache.clear()
    _session_factory_cache.clear()
