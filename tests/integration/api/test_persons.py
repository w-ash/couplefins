from httpx import AsyncClient

from tests.integration.conftest import setup_and_login, setup_couple


async def test_setup_couple_creates_two_persons(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={
            "name1": "Alice",
            "name2": "Bob",
            "password1": "password123",
            "password2": "password456",
        },
    )
    assert response.status_code == 201
    persons = response.json()
    assert len(persons) == 2
    assert persons[0]["name"] == "Alice"
    assert persons[1]["name"] == "Bob"
    assert persons[0]["id"] != persons[1]["id"]
    assert not persons[0]["adjustment_account"]


async def test_setup_couple_then_list(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get("/api/v1/persons/", cookies=cookies)
    assert response.status_code == 200
    persons = response.json()
    assert len(persons) == 2
    names = {p["name"] for p in persons}
    assert names == {"Alice", "Bob"}


async def test_setup_couple_rejects_duplicate_setup(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.post(
        "/api/v1/persons/setup",
        json={
            "name1": "Charlie",
            "name2": "Dana",
            "password1": "password123",
            "password2": "password456",
        },
    )
    assert response.status_code == 409
    assert "already set up" in response.json()["error"]["message"]


async def test_setup_couple_rejects_identical_names(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/persons/setup",
        json={
            "name1": "Alice",
            "name2": "alice",
            "password1": "password123",
            "password2": "password456",
        },
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
    # No setup needed; GET /persons/ requires auth but no persons exist yet.
    # Without auth, this should return 401.
    response = await client.get("/api/v1/persons/")
    assert response.status_code == 401


async def test_list_persons_authenticated(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get("/api/v1/persons/", cookies=cookies)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_patch_person_updates_adjustment_account(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    response = await client.patch(
        f"/api/v1/persons/{person_id}",
        json={"adjustment_account": "Shared Adjustments"},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json()["adjustment_account"] == "Shared Adjustments"
    assert response.json()["name"] == "Alice"

    get_resp = await client.get("/api/v1/persons/", cookies=cookies)
    alice = next(p for p in get_resp.json() if p["id"] == person_id)
    assert alice["adjustment_account"] == "Shared Adjustments"


async def test_patch_person_not_found(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.patch(
        "/api/v1/persons/00000000-0000-0000-0000-000000000000",
        json={"adjustment_account": "Test"},
        cookies=cookies,
    )
    assert response.status_code == 404


async def test_patch_person_rejects_blank_account(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    response = await client.patch(
        f"/api/v1/persons/{person_id}",
        json={"adjustment_account": "   "},
        cookies=cookies,
    )
    assert response.status_code == 422
