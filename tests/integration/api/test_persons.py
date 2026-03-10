from httpx import AsyncClient


async def test_setup_couple_creates_two_persons(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={"name1": "Alice", "name2": "Bob"},
    )
    assert response.status_code == 201
    persons = response.json()
    assert len(persons) == 2
    assert persons[0]["name"] == "Alice"
    assert persons[1]["name"] == "Bob"
    assert persons[0]["id"] != persons[1]["id"]
    assert not persons[0]["adjustment_account"]


async def test_setup_couple_then_list(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/persons/setup",
        json={"name1": "Alice", "name2": "Bob"},
    )

    response = await client.get("/api/v1/persons/")
    assert response.status_code == 200
    persons = response.json()
    assert len(persons) == 2
    names = {p["name"] for p in persons}
    assert names == {"Alice", "Bob"}


async def test_setup_couple_rejects_duplicate_setup(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/persons/setup",
        json={"name1": "Alice", "name2": "Bob"},
    )

    response = await client.post(
        "/api/v1/persons/setup",
        json={"name1": "Charlie", "name2": "Dana"},
    )
    assert response.status_code == 409
    assert "already set up" in response.json()["error"]["message"]


async def test_setup_couple_rejects_identical_names(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={"name1": "Alice", "name2": "alice"},
    )
    assert response.status_code == 422
    assert "different" in response.json()["error"]["message"]


async def test_setup_couple_rejects_blank_names(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={"name1": "", "name2": "Bob"},
    )
    assert response.status_code == 422


async def test_setup_couple_rejects_whitespace_only_names(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={"name1": "   ", "name2": "Bob"},
    )
    assert response.status_code == 422


async def test_list_persons_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/persons/")
    assert response.status_code == 200
    assert response.json() == []
