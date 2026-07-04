from httpx import AsyncClient
import pytest

from tests.integration.conftest import login_as_bob, setup_and_login, upload_csv

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
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE, cookies=cookies)
    bob_cookies = await login_as_bob(client)
    await upload_csv(client, bob_id, SHARED_CSV_BOB, cookies=bob_cookies)

    response = await client.get("/api/v1/dashboard?year=2026&month=1", cookies=cookies)
    assert response.status_code == 200

    data = response.json()
    assert data["current_month_year"] == 2026
    assert data["current_month_month"] == 1
    assert data["current_month_transaction_count"] == 3
    assert data["current_month_total_household_spending"] == pytest.approx(200.0)
    assert data["current_month_settlement"] is not None
    assert len(data["upload_statuses"]) == 2
    assert all(s["has_uploaded"] for s in data["upload_statuses"])


async def test_now_card_and_month_history_household_spending_agree(
    client: AsyncClient,
) -> None:
    """A household no-split row (household tag, no sXX) plus a shared split
    row in the same month: the now-card's household_spending_month and the
    Month History entry for that month must report the same figure."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-60.00",shared\n'
        '2026-01-16,Concert,Lifestyle,Amex,CONCERT,,"-40.00",household\n'
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get("/api/v1/dashboard?year=2026&month=1", cookies=cookies)
    assert response.status_code == 200
    data = response.json()

    jan = next(m for m in data["month_history"] if m["month"] == 1)
    assert data["household_spending_month"] == pytest.approx(100.0)
    assert jan["total_household_spending"] == pytest.approx(
        data["household_spending_month"]
    )


async def test_dashboard_month_history(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE, cookies=cookies)

    response = await client.get("/api/v1/dashboard?year=2026&month=2", cookies=cookies)
    assert response.status_code == 200

    data = response.json()
    # Should have data in both Jan and Feb
    assert len(data["month_history"]) == 2
    # Newest first
    assert data["month_history"][0]["month"] == 2
    assert data["month_history"][1]["month"] == 1


async def test_dashboard_ytd_aggregation(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV_ALICE, cookies=cookies)

    response = await client.get("/api/v1/dashboard?year=2026&month=2", cookies=cookies)
    data = response.json()

    # YTD should include Jan ($100 + $60) + Feb ($20) = $180
    assert data["household_spending_ytd"] == pytest.approx(180.0)


async def test_dashboard_defaults_to_current_month(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get("/api/v1/dashboard", cookies=cookies)
    assert response.status_code == 200

    data = response.json()
    # Should default to some year/month (current)
    assert data["current_month_year"] > 0
    assert 1 <= data["current_month_month"] <= 12


async def test_dashboard_empty_month(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get("/api/v1/dashboard?year=2026&month=6", cookies=cookies)
    assert response.status_code == 200

    data = response.json()
    assert data["current_month_transaction_count"] == 0
    assert data["current_month_total_household_spending"] == pytest.approx(0.0)
    assert data["month_history"] == []
    assert all(not s["has_uploaded"] for s in data["upload_statuses"])
