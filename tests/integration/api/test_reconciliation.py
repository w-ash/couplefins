from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_and_login, upload_csv

SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
    '2026-01-16,Restaurant,Dining Out,Amex,RESTAURANT,,"-60.00","shared,s70"\n'
)

SHARED_CSV_BOB = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-20,Gas Station,Gas,Chase,GAS STATION,,"-40.00",shared\n'
)


async def test_full_reconciliation_both_uploaded(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    await upload_csv(client, alice_id, SHARED_CSV, cookies=cookies)
    await upload_csv(client, bob_id, SHARED_CSV_BOB, cookies=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200

    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert data["start_date"] == "2026-01-01"
    assert data["end_date"] == "2026-01-31"
    assert data["transaction_count"] == 3
    assert data["total_shared_spending"] == pytest.approx(200.0)
    assert data["settlement"] is not None
    assert data["settlement"]["amount"] > 0
    assert len(data["transactions"]) == 3
    assert len(data["upload_statuses"]) == 2
    assert all(s["has_uploaded"] for s in data["upload_statuses"])


async def test_partial_upload_one_person(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV, cookies=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200

    data = response.json()
    assert data["transaction_count"] == 2

    statuses = {s["person_name"]: s for s in data["upload_statuses"]}
    assert statuses["Alice"]["has_uploaded"] is True
    assert statuses["Bob"]["has_uploaded"] is False


async def test_empty_month_no_data(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=3", cookies=cookies
    )
    assert response.status_code == 200

    data = response.json()
    assert data["transaction_count"] == 0
    assert data["total_shared_spending"] == pytest.approx(0.0)
    assert data["transactions"] == []
    assert data["settlement"]["amount"] == pytest.approx(0.0)


async def test_settlement_math(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    # Alice pays $100 at 50/50 → Bob owes $50
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-02-15,Test,Dining Out,Chase,TEST,,"-100.00",shared\n'
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=2", cookies=cookies
    )
    data = response.json()

    assert data["settlement"]["amount"] == pytest.approx(50.0)
    # Bob (persons[1]) owes Alice (persons[0])
    assert data["settlement"]["from_person_id"] == persons[1]["id"]
    assert data["settlement"]["to_person_id"] == persons[0]["id"]


async def test_date_range_query(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv_jan = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Test,Dining Out,Chase,TEST,,"-100.00",shared\n'
    )
    csv_feb = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-02-10,Test2,Dining Out,Chase,TEST2,,"-60.00",shared\n'
    )
    await upload_csv(client, alice_id, csv_jan, cookies=cookies)
    await upload_csv(client, alice_id, csv_feb, cookies=cookies)

    response = await client.get(
        "/api/v1/reconciliation?start_date=2026-01-01&end_date=2026-02-28",
        cookies=cookies,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["start_date"] == "2026-01-01"
    assert data["end_date"] == "2026-02-28"
    assert data["transaction_count"] == 2
    assert data["total_shared_spending"] == pytest.approx(160.0)
    # Multi-month range → year/month are None, is_finalized is None
    assert data["year"] is None
    assert data["month"] is None
    assert data["is_finalized"] is None


async def test_mixed_params_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1&start_date=2026-01-01&end_date=2026-01-31",
        cookies=cookies,
    )
    assert response.status_code == 422


async def test_partial_range_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get(
        "/api/v1/reconciliation?start_date=2026-01-01", cookies=cookies
    )
    assert response.status_code == 422


PERSONAL_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Coffee,Dining Out,Chase,COFFEE,,"-5.00",\n'
)


async def test_reconciliation_personal_scope(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    # Upload shared + personal transactions for Alice
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Restaurant,Dining Out,Chase,REST,,"-100.00",shared\n'
        '2026-01-16,Coffee,Dining Out,Chase,COFFEE,,"-5.00",\n'
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    # Personal scope: only Alice's non-household txs
    response = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=personal&person_id={alice_id}",
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_count"] == 0  # personal txs have payer_percentage=100
    assert len(data["transactions"]) == 1  # the coffee tx (non-household)


async def test_reconciliation_all_scope(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Restaurant,Dining Out,Chase,REST,,"-100.00",shared\n'
        '2026-01-16,Coffee,Dining Out,Chase,COFFEE,,"-5.00",\n'
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=all&person_id={alice_id}",
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    # Both shared restaurant and personal coffee
    assert len(data["transactions"]) == 2


async def test_reconciliation_default_scope_unchanged(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Restaurant,Dining Out,Chase,REST,,"-100.00",shared\n'
        '2026-01-16,Coffee,Dining Out,Chase,COFFEE,,"-5.00",\n'
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()
    # Default household scope: only shared restaurant
    assert len(data["transactions"]) == 1
