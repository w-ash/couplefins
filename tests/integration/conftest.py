from collections.abc import AsyncGenerator
import os

from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings, reset_settings
from src.infrastructure.persistence.database.db_connection import run_migrations
from src.infrastructure.persistence.models import Base

load_dotenv()

ALICE_PASSWORD = "password123"
BOB_PASSWORD = "password456"


def _get_test_db_url() -> str:
    url = os.environ.get("TEST_DATABASE__URL", "")
    if not url:
        pytest.skip("TEST_DATABASE__URL not set — skipping integration tests")
    if "-pooler" in url:
        msg = (
            "TEST_DATABASE__URL contains '-pooler', which looks like a production "
            "Neon endpoint. Use a non-pooled endpoint or a dedicated test branch. "
            "Integration tests TRUNCATE all tables on teardown."
        )
        raise RuntimeError(msg)
    return url


async def _truncate_all(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE " + ", ".join(Base.metadata.tables) + " CASCADE")
        )


@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema() -> None:
    # Drop before upgrading so stale state — e.g. tables without an
    # alembic_version row — can't trip the migration with DuplicateTable.
    os.environ["DATABASE__URL"] = _get_test_db_url()
    reset_settings()
    sync_url = get_settings().database.sync_url
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()
    run_migrations(sync_url)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(_get_test_db_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await _truncate_all(engine)
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
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

    from src.application.runner import execute_use_case
    from src.application.use_cases.seed_category_groups import seed_category_groups
    from src.application.use_cases.seed_settlement_merchants import (
        seed_settlement_merchants,
    )

    app = create_app()
    await execute_use_case(seed_category_groups)
    await execute_use_case(seed_settlement_merchants)

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
    password1: str = ALICE_PASSWORD,
    password2: str = BOB_PASSWORD,
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
    password: str = ALICE_PASSWORD,
) -> dict[str, str]:
    """Log in and return cookies dict for subsequent requests."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"name": name, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return dict(resp.cookies)


async def login_as_bob(client: AsyncClient) -> dict[str, str]:
    """Log in as Bob and return cookies."""
    return await login_as(client, "Bob", BOB_PASSWORD)


async def setup_and_login(
    client: AsyncClient,
    password1: str = ALICE_PASSWORD,
    password2: str = BOB_PASSWORD,
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
