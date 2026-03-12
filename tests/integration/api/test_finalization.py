from httpx import AsyncClient

from tests.integration.conftest import setup_couple


async def test_finalize_creates_period(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1, "notes": "Reviewed together"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None
    assert data["notes"] == "Reviewed together"


async def test_finalize_already_finalized_returns_422(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 2}
    )
    response = await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 2}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unfinalize_period(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 3}
    )
    response = await client.post(
        "/api/v1/reconciliation/unfinalize", json={"year": 2026, "month": 3}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is False
    assert data["finalized_at"] is None


async def test_unfinalize_not_finalized_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/reconciliation/unfinalize", json={"year": 2026, "month": 4}
    )
    assert response.status_code == 422


async def test_period_status_not_finalized(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/reconciliation/period-status?year=2026&month=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is False
    assert data["finalized_at"] is None


async def test_period_status_finalized(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 6, "notes": "Done"},
    )
    response = await client.get(
        "/api/v1/reconciliation/period-status?year=2026&month=6"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["notes"] == "Done"


async def test_upload_to_finalized_month_returns_409(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 1}
    )

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Dining Out,Chase,,,-50.00,shared\n"
    )
    import io

    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": alice_id},
        files={"file": ("test.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERIOD_FINALIZED"


async def test_reconciliation_includes_finalization_status(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 7, "notes": "July done"},
    )
    response = await client.get("/api/v1/reconciliation?year=2026&month=7")
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None


async def test_dashboard_includes_finalization_status(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 8}
    )
    response = await client.get("/api/v1/dashboard?year=2026&month=8")
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None
