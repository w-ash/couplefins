from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database_host" in data
    assert "database_mode" in data


async def test_liveness_returns_ok(client: AsyncClient) -> None:
    # The platform health check probes this; it must answer without a query.
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_liveness_is_absent_from_the_openapi_schema(
    client: AsyncClient,
) -> None:
    # Keeping it out of the spec keeps it out of the generated client, so the
    # frontend never depends on a platform-only endpoint.
    response = await client.get("/api/openapi.json")
    assert "/api/v1/health/live" not in response.json()["paths"]
