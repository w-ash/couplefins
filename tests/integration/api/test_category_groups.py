from httpx import AsyncClient


async def test_list_category_groups(client: AsyncClient) -> None:
    response = await client.get("/api/v1/category-groups")
    assert response.status_code == 200
    groups = response.json()
    assert isinstance(groups, list)


async def test_create_category_group(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/category-groups",
        json={"name": "Test Group"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Group"
    assert "id" in data
    assert data["categories"] == []


async def test_update_category_group(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "Old Name"},
    )
    group_id = create.json()["id"]

    response = await client.put(
        f"/api/v1/category-groups/{group_id}",
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_delete_category_group(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "To Delete"},
    )
    group_id = create.json()["id"]

    response = await client.delete(f"/api/v1/category-groups/{group_id}")
    assert response.status_code == 204


async def test_delete_nonexistent_group_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/category-groups/{fake_id}")
    assert response.status_code == 404


async def test_bulk_update_mappings(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/category-groups",
        json={"name": "Mapping Group"},
    )
    group_id = create.json()["id"]

    response = await client.put(
        "/api/v1/category-mappings",
        json={
            "mappings": [
                {"category": "Groceries", "group_id": group_id},
                {"category": "Dining Out", "group_id": group_id},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2


async def test_unmapped_categories_empty_when_no_transactions(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/category-mappings/unmapped")
    assert response.status_code == 200
    assert response.json() == []
