from httpx import AsyncClient

from tests.integration.conftest import setup_and_login


async def test_candidates_returns_list(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/settlements/candidates",
        params={"year": 2026, "month": 3, "amount": 100.0},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_candidates_requires_auth(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/settlements/candidates",
        params={"year": 2026, "month": 3, "amount": 100.0},
    )
    assert response.status_code in {401, 403}


async def test_unlink_requires_auth(client: AsyncClient) -> None:
    response = await client.delete(
        "/api/v1/settlements/00000000-0000-0000-0000-000000000001/links/00000000-0000-0000-0000-000000000002",
    )
    assert response.status_code in {401, 403}
