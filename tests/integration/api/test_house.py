from httpx import AsyncClient

from tests.integration.conftest import setup_and_login, setup_couple

_SECTIONS = ("put_in", "shares", "loans", "upcoming", "set_aside", "recent_activity")


async def test_house_serves_the_example_with_every_section_filled(
    client: AsyncClient,
) -> None:
    _, auth = await setup_and_login(client)

    response = await client.get("/api/v1/house", auth=auth)

    assert response.status_code == 200
    data = response.json()
    assert data["is_example"] is True
    assert [p["name"] for p in data["persons"]] == ["Alice", "Bob"]
    for section in _SECTIONS:
        assert data[section], section
    assert isinstance(data["put_in"]["total"], float)
    assert isinstance(data["shares"]["now"][0]["percent"], float)
    assert isinstance(data["loans"][0]["owner_parts"][0]["amount"], float)


async def test_house_requires_login(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.get("/api/v1/house")

    assert response.status_code == 401
