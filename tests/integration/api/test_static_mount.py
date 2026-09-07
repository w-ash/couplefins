from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from src.config.constants import AppConfig
from src.interface.api.app import _mount_static, create_app
from src.interface.api.error_handling import register_error_handlers
from src.interface.api.routes.health import router as health_router

INDEX_BODY = "<!doctype html><title>Couplefins</title>"
FAVICON_BODY = "<svg />"
ASSET_BODY = "console.log(1)"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal stand-in for a real `pnpm build` output tree."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text(ASSET_BODY)
    (tmp_path / "index.html").write_text(INDEX_BODY)
    (tmp_path / "favicon.svg").write_text(FAVICON_BODY)
    return tmp_path


@pytest.fixture
async def static_client(dist: Path) -> AsyncClient:
    """An app wired like create_app() but serving a temporary build tree.

    Built by hand rather than from create_app() because create_app() already
    mounts the real web/dist when the developer has run `pnpm build`, and the
    first catch-all registered is the one that answers.
    """
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(health_router, prefix=AppConfig.API_V1_PREFIX)
    _mount_static(app, dist)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_root_serves_index(static_client: AsyncClient) -> None:
    response = await static_client.get("/")
    assert response.status_code == 200
    assert response.text == INDEX_BODY


async def test_client_route_serves_index(static_client: AsyncClient) -> None:
    # A React Router deep link is not a file on disk; it must still render.
    response = await static_client.get("/settle-up")
    assert response.status_code == 200
    assert response.text == INDEX_BODY


async def test_real_file_is_served(static_client: AsyncClient) -> None:
    response = await static_client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.text == FAVICON_BODY


async def test_real_file_is_served_with_a_query_string(
    static_client: AsyncClient,
) -> None:
    # index.html references the favicon with a cache-busting ?v= suffix.
    response = await static_client.get("/favicon.svg?v=13")
    assert response.status_code == 200
    assert response.text == FAVICON_BODY


async def test_hashed_asset_is_served(static_client: AsyncClient) -> None:
    response = await static_client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.text == ASSET_BODY


async def test_unknown_api_path_is_not_swallowed(static_client: AsyncClient) -> None:
    # The catch-all must never answer for /api, and the 404 must carry the
    # error envelope the frontend parses — a bare HTTPException would not.
    response = await static_client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_registered_api_route_still_wins(static_client: AsyncClient) -> None:
    response = await static_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_path_traversal_falls_back_to_index(static_client: AsyncClient) -> None:
    response = await static_client.get("/..%2f..%2fetc%2fpasswd")
    assert response.status_code == 200
    assert response.text == INDEX_BODY


async def test_mount_is_a_noop_without_a_build(tmp_path: Path) -> None:
    # Development and CI have no web/dist; the app must be left untouched.
    app = FastAPI()
    _mount_static(app, tmp_path)
    assert [route.path for route in app.routes if "{path" in route.path] == []


def test_catchall_is_registered_last(
    dist: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ordering is the whole contract: Starlette matches in registration order,
    # so a router added after the catch-all would be unreachable. Pointed at a
    # temporary build so this holds in CI, where web/dist does not exist.
    monkeypatch.setattr("src.interface.api.app._WEB_DIST", dist)
    paths = [route.path for route in create_app().routes]
    assert paths[-1] == "/{path:path}"
