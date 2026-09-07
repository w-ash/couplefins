import asyncio
from collections.abc import AsyncIterator
import contextlib
import json

from httpx import AsyncClient

from src.infrastructure.events.event_bus import event_bus
from tests.integration.conftest import setup_and_login


@contextlib.asynccontextmanager
async def _sse_queue() -> AsyncIterator[asyncio.Queue[str]]:
    queue = event_bus.subscribe()
    try:
        yield queue
    finally:
        event_bus.unsubscribe(queue)


def _entities(queue: asyncio.Queue[str]) -> list[str]:
    events: list[str] = []
    while not queue.empty():
        events.append(json.loads(queue.get_nowait())["entity"])
    return events


async def test_list_category_groups(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get("/api/v1/category-groups", auth=cookies)
    assert response.status_code == 200
    groups = response.json()
    assert isinstance(groups, list)


async def test_create_category_group(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/category-groups",
        json={"name": "Test Group"},
        auth=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Group"
    assert "id" in data
    assert data["categories"] == []


async def test_update_category_group(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "Old Name"},
        auth=cookies,
    )
    group_id = create.json()["id"]

    response = await client.put(
        f"/api/v1/category-groups/{group_id}",
        json={"name": "New Name", "kind": "expense"},
        auth=cookies,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_delete_category_group(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "To Delete"},
        auth=cookies,
    )
    group_id = create.json()["id"]

    response = await client.delete(f"/api/v1/category-groups/{group_id}", auth=cookies)
    assert response.status_code == 204


async def test_delete_nonexistent_group_returns_404(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/category-groups/{fake_id}", auth=cookies)
    assert response.status_code == 404


async def test_bulk_update_mappings(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "Mapping Group"},
        auth=cookies,
    )
    group_id = create.json()["id"]

    response = await client.put(
        "/api/v1/category-mappings",
        json={
            "mappings": [
                {"category": "Groceries", "group_id": group_id},
                {"category": "Restaurants & Bars", "group_id": group_id},
            ]
        },
        auth=cookies,
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2


async def test_unmapped_categories_empty_when_no_transactions(
    client: AsyncClient,
) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get("/api/v1/category-mappings/unmapped", auth=cookies)
    assert response.status_code == 200
    assert response.json() == []


async def test_seeded_groups_carry_their_kind(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    groups = (await client.get("/api/v1/category-groups", auth=cookies)).json()
    kinds = {g["name"]: g["kind"] for g in groups}
    assert kinds["Transfers"] == "transfer"
    assert kinds["Income"] == "income"
    assert kinds["Food & Dining"] == "expense"


async def test_group_kind_round_trips(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "Card Payments", "kind": "transfer"},
        auth=cookies,
    )
    assert create.status_code == 201
    assert create.json()["kind"] == "transfer"
    group_id = create.json()["id"]

    update = await client.put(
        f"/api/v1/category-groups/{group_id}",
        json={"name": "Card Payments", "kind": "expense"},
        auth=cookies,
    )
    assert update.status_code == 200
    assert update.json()["kind"] == "expense"

    listed = (await client.get("/api/v1/category-groups", auth=cookies)).json()
    assert next(g["kind"] for g in listed if g["id"] == group_id) == "expense"


async def test_group_create_defaults_to_expense(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/category-groups", json={"name": "Plain"}, auth=cookies
    )
    assert create.json()["kind"] == "expense"


async def test_every_mutation_broadcasts_category_groups(
    client: AsyncClient,
) -> None:
    """A partner's open Dashboard, Budget, and Settle Up recompute from a
    group's kind and each category's group, so every write announces itself."""
    _, cookies = await setup_and_login(client)
    async with _sse_queue() as queue:
        created = await client.post(
            "/api/v1/category-groups", json={"name": "Cards"}, auth=cookies
        )
        group_id = created.json()["id"]
        assert _entities(queue) == ["category_groups"]

        await client.put(
            f"/api/v1/category-groups/{group_id}",
            json={"name": "Cards", "kind": "transfer"},
            auth=cookies,
        )
        assert _entities(queue) == ["category_groups"]

        await client.put(
            "/api/v1/category-mappings",
            json={"mappings": [{"category": "Card Payment", "group_id": group_id}]},
            auth=cookies,
        )
        assert _entities(queue) == ["category_groups"]

        await client.patch(
            "/api/v1/categories/Card Payment",
            json={"include_personal": True},
            auth=cookies,
        )
        assert _entities(queue) == ["category_groups"]

        await client.delete(f"/api/v1/category-groups/{group_id}", auth=cookies)
        assert _entities(queue) == ["category_groups"]
