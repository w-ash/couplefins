from httpx import AsyncClient

from tests.integration.conftest import setup_and_login


async def test_list_returns_seeded_merchants(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get("/api/v1/settings/settlement-merchants", auth=cookies)
    assert response.status_code == 200
    merchants = response.json()
    assert isinstance(merchants, list)
    names = {m["name"] for m in merchants}
    assert "Venmo" in names
    assert "Zelle" in names
    assert "Cash App" in names


async def test_create_merchant(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/settings/settlement-merchants",
        json={"name": "PayPal", "merchant_pattern": "paypal"},
        auth=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "PayPal"
    assert data["merchant_pattern"] == "paypal"
    assert "id" in data


async def test_delete_merchant(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    create = await client.post(
        "/api/v1/settings/settlement-merchants",
        json={"name": "Wise", "merchant_pattern": "wise"},
        auth=cookies,
    )
    merchant_id = create.json()["id"]

    response = await client.delete(
        f"/api/v1/settings/settlement-merchants/{merchant_id}", auth=cookies
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True


async def test_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/settlement-merchants")
    assert response.status_code in {401, 403}
