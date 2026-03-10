from httpx import AsyncClient


async def test_create_and_list_persons(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/",
        json={"name": "Alice", "adjustment_account": "Adjustments"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert data["adjustment_account"] == "Adjustments"
    assert "id" in data

    response = await client.get("/api/v1/persons/")
    assert response.status_code == 200
    persons = response.json()
    assert len(persons) >= 1
    assert any(p["name"] == "Alice" for p in persons)


async def test_list_persons_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/persons/")
    assert response.status_code == 200
    assert response.json() == []
