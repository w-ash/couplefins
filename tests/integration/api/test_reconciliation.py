from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_couple, upload_csv

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
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    await upload_csv(client, alice_id, SHARED_CSV)
    await upload_csv(client, bob_id, SHARED_CSV_BOB)

    response = await client.get("/api/v1/reconciliation?year=2026&month=1")
    assert response.status_code == 200

    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert data["transaction_count"] == 3
    assert data["total_shared_spending"] == pytest.approx(200.0)
    assert data["settlement"] is not None
    assert data["settlement"]["amount"] > 0
    assert len(data["transactions"]) == 3
    assert len(data["upload_statuses"]) == 2
    assert all(s["has_uploaded"] for s in data["upload_statuses"])


async def test_partial_upload_one_person(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV)

    response = await client.get("/api/v1/reconciliation?year=2026&month=1")
    assert response.status_code == 200

    data = response.json()
    assert data["transaction_count"] == 2

    statuses = {s["person_name"]: s for s in data["upload_statuses"]}
    assert statuses["Alice"]["has_uploaded"] is True
    assert statuses["Bob"]["has_uploaded"] is False


async def test_empty_month_no_data(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.get("/api/v1/reconciliation?year=2026&month=3")
    assert response.status_code == 200

    data = response.json()
    assert data["transaction_count"] == 0
    assert data["total_shared_spending"] == pytest.approx(0.0)
    assert data["transactions"] == []
    assert data["settlement"]["amount"] == pytest.approx(0.0)


async def test_settlement_math(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    # Alice pays $100 at 50/50 → Bob owes $50
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-02-15,Test,Dining Out,Chase,TEST,,"-100.00",shared\n'
    )
    await upload_csv(client, alice_id, csv)

    response = await client.get("/api/v1/reconciliation?year=2026&month=2")
    data = response.json()

    assert data["settlement"]["amount"] == pytest.approx(50.0)
    # Bob (persons[1]) owes Alice (persons[0])
    assert data["settlement"]["from_person_id"] == persons[1]["id"]
    assert data["settlement"]["to_person_id"] == persons[0]["id"]
