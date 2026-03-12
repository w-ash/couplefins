from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_couple, upload_csv

SHARED_CSV_ALICE = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
    '2026-01-16,Restaurant,Dining Out,Amex,RESTAURANT,,"-60.00","shared,s70"\n'
    '2026-02-10,Coffee Shop,Coffee,Chase,COFFEE SHOP,,"-20.00",shared\n'
)

SHARED_CSV_BOB = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-20,Gas Station,Gas,Chase,GAS STATION,,"-40.00",shared\n'
)


async def test_dashboard_with_data(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE)
    await upload_csv(client, bob_id, SHARED_CSV_BOB)

    response = await client.get("/api/v1/dashboard?year=2026&month=1")
    assert response.status_code == 200

    data = response.json()
    assert data["current_month_year"] == 2026
    assert data["current_month_month"] == 1
    assert data["current_month_transaction_count"] == 3
    assert data["current_month_total_shared_spending"] == pytest.approx(200.0)
    assert data["current_month_settlement"] is not None
    assert len(data["upload_statuses"]) == 2
    assert all(s["has_uploaded"] for s in data["upload_statuses"])


async def test_dashboard_month_history(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE)

    response = await client.get("/api/v1/dashboard?year=2026&month=2")
    assert response.status_code == 200

    data = response.json()
    # Should have data in both Jan and Feb
    assert len(data["month_history"]) == 2
    # Newest first
    assert data["month_history"][0]["month"] == 2
    assert data["month_history"][1]["month"] == 1


async def test_dashboard_ytd_aggregation(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE)

    response = await client.get("/api/v1/dashboard?year=2026&month=2")
    data = response.json()

    # YTD should include Jan ($100 + $60) + Feb ($20) = $180
    assert data["ytd_total_shared_spending"] == pytest.approx(180.0)


async def test_dashboard_defaults_to_current_month(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.get("/api/v1/dashboard")
    assert response.status_code == 200

    data = response.json()
    # Should default to some year/month (current)
    assert data["current_month_year"] > 0
    assert 1 <= data["current_month_month"] <= 12


async def test_dashboard_empty_month(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.get("/api/v1/dashboard?year=2026&month=6")
    assert response.status_code == 200

    data = response.json()
    assert data["current_month_transaction_count"] == 0
    assert data["current_month_total_shared_spending"] == pytest.approx(0.0)
    assert data["month_history"] == []
    assert all(not s["has_uploaded"] for s in data["upload_statuses"])
