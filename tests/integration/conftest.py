from collections.abc import AsyncGenerator
import os

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import from models/__init__ (not models.base) to ensure all models register with Base.metadata
from src.infrastructure.persistence.models import Base


def _get_test_db_url() -> str:
    url = os.environ.get("DATABASE__URL", "")
    if not url:
        pytest.skip("DATABASE__URL not set — skipping integration tests")
    return url


async def _truncate_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE " + ", ".join(Base.metadata.tables) + " CASCADE")
        )


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    url = _get_test_db_url()
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await _truncate_all(engine)
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    from src.config.settings import reset_settings
    from src.infrastructure.persistence.database.db_connection import (
        _get_engine,
        dispose_engine,
        reset_engine_cache,
    )
    from src.interface.api.app import create_app

    url = _get_test_db_url()
    os.environ["DATABASE__URL"] = url
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

    await _truncate_all(_get_engine())
    await dispose_engine()
    reset_settings()


async def setup_couple(
    client: AsyncClient,
    password1: str = "password123",
    password2: str = "password456",
) -> list[dict]:
    """Create a couple (Alice & Bob) and return the person dicts."""
    resp = await client.post(
        "/api/v1/persons/setup",
        json={
            "name1": "Alice",
            "name2": "Bob",
            "password1": password1,
            "password2": password2,
        },
    )
    return resp.json()


async def login_as(
    client: AsyncClient,
    name: str = "Alice",
    password: str = "password123",
) -> dict[str, str]:
    """Log in and return cookies dict for subsequent requests."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"name": name, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return dict(resp.cookies)


async def setup_and_login(
    client: AsyncClient,
    password1: str = "password123",
    password2: str = "password456",
) -> tuple[list[dict], dict[str, str]]:
    """Create couple, log in as Alice, return (persons, cookies)."""
    persons = await setup_couple(client, password1=password1, password2=password2)
    cookies = await login_as(client, "Alice", password1)
    return persons, cookies


async def upload_csv(
    client: AsyncClient,
    person_id: str,
    csv_text: str,
    cookies: dict[str, str] | None = None,
) -> dict:
    """Upload a CSV string for a person and return the response JSON."""
    import io

    resp = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(csv_text.encode()), "text/csv")},
        cookies=cookies,
    )
    return resp.json()
