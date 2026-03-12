import csv
import io

from httpx import AsyncClient

from tests.integration.conftest import setup_couple, upload_csv

SHARED_CSV_ALICE = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
    '2026-01-16,Restaurant,Dining Out,Amex,RESTAURANT,,"-60.00","shared,s70"\n'
)

SHARED_CSV_BOB = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-20,Gas Station,Gas,Chase,GAS STATION,,"-40.00",shared\n'
)


async def _setup_with_accounts(client: AsyncClient) -> tuple[str, str]:
    """Create couple and set adjustment accounts. Returns (alice_id, bob_id)."""
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    await client.patch(
        f"/api/v1/persons/{alice_id}",
        json={"adjustment_account": "Alice Adjustments"},
    )
    await client.patch(
        f"/api/v1/persons/{bob_id}",
        json={"adjustment_account": "Bob Adjustments"},
    )
    return alice_id, bob_id


async def test_export_full_flow(client: AsyncClient) -> None:
    alice_id, bob_id = await _setup_with_accounts(client)
    await upload_csv(client, alice_id, SHARED_CSV_ALICE)
    await upload_csv(client, bob_id, SHARED_CSV_BOB)

    response = await client.get(f"/api/v1/persons/{alice_id}/export/2026/1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "adjustments-alice-2026-01.csv" in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "Date",
        "Amount",
        "Merchant",
        "Category",
        "Account",
        "Tags",
        "Notes",
    ]
    assert len(rows) > 1  # at least one data row
    # All data rows should have couplefins-adjustment tag
    for row in rows[1:]:
        assert row[5] == "couplefins-adjustment"
        assert row[6].startswith("[cf:")


async def test_export_bob_perspective(client: AsyncClient) -> None:
    alice_id, bob_id = await _setup_with_accounts(client)
    await upload_csv(client, alice_id, SHARED_CSV_ALICE)
    await upload_csv(client, bob_id, SHARED_CSV_BOB)

    response = await client.get(f"/api/v1/persons/{bob_id}/export/2026/1")
    assert response.status_code == 200
    assert "adjustments-bob-2026-01.csv" in response.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(response.text)))
    # Bob's adjustments should have his account name
    for row in rows[1:]:
        assert row[4] == "Bob Adjustments"


async def test_export_person_not_found(client: AsyncClient) -> None:
    await _setup_with_accounts(client)
    response = await client.get(
        "/api/v1/persons/00000000-0000-0000-0000-000000000000/export/2026/1"
    )
    assert response.status_code == 404


async def test_export_without_adjustment_account(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    response = await client.get(f"/api/v1/persons/{alice_id}/export/2026/1")
    assert response.status_code == 422
    assert "not configured" in response.json()["error"]["message"]


async def test_export_empty_month(client: AsyncClient) -> None:
    alice_id, _ = await _setup_with_accounts(client)

    response = await client.get(f"/api/v1/persons/{alice_id}/export/2026/3")
    assert response.status_code == 200

    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 1  # header only


async def test_export_idempotent(client: AsyncClient) -> None:
    alice_id, bob_id = await _setup_with_accounts(client)
    await upload_csv(client, alice_id, SHARED_CSV_ALICE)
    await upload_csv(client, bob_id, SHARED_CSV_BOB)

    first = await client.get(f"/api/v1/persons/{alice_id}/export/2026/1")
    second = await client.get(f"/api/v1/persons/{alice_id}/export/2026/1")
    assert first.text == second.text
