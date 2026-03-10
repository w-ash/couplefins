from collections.abc import AsyncGenerator
import os
import pathlib
import tempfile

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.persistence.models.base import Base


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    from src.config.settings import reset_settings
    from src.infrastructure.persistence.database.db_connection import (
        dispose_engine,
        reset_engine_cache,
    )
    from src.interface.api.app import create_app

    # Use a temp file DB so tables persist across connections
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE__URL"] = f"sqlite+aiosqlite:///{db_path}"
    reset_settings()
    reset_engine_cache()

    from src.infrastructure.persistence.database.db_connection import init_db

    app = create_app()
    await init_db()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Clean up
    await dispose_engine()
    reset_settings()
    os.environ.pop("DATABASE__URL", None)
    pathlib.Path(db_path).unlink()  # noqa: ASYNC240
