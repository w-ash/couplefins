from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings
from src.infrastructure.persistence.models import Base

_engine_cache: list[AsyncEngine] = []
_session_factory_cache: list[async_sessionmaker[AsyncSession]] = []


def _get_engine() -> AsyncEngine:
    if not _engine_cache:
        settings = get_settings()
        _engine_cache.append(
            create_async_engine(settings.database.url, echo=settings.database.echo)
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


async def init_db() -> None:
    settings = get_settings()
    parts = settings.database.url.partition("///")
    if parts[2]:
        Path(parts[2]).parent.mkdir(parents=True, exist_ok=True)
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    if _engine_cache:
        await _engine_cache[0].dispose()
    reset_engine_cache()


def reset_engine_cache() -> None:
    _engine_cache.clear()
    _session_factory_cache.clear()
