from httpx import AsyncClient
import pytest

from tests.integration.conftest import login_as_bob, setup_and_login, upload_csv

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

    await upload_csv(client, alice_id, SHARED_CSV, auth=cookies)
    bob_cookies = await login_as_bob(client)
    await upload_csv(client, bob_id, SHARED_CSV_BOB, auth=bob_cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200

    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert data["start_date"] == "2026-01-01"
    assert data["end_date"] == "2026-01-31"
    assert data["transaction_count"] == 3
    assert data["total_household_spending"] == pytest.approx(200.0)
    assert data["settlement"] is not None
    assert data["settlement"]["amount"] > 0
    assert len(data["transactions"]) == 3
    assert all(tx["is_settlement"] is False for tx in data["transactions"])
    assert len(data["upload_statuses"]) == 2
    assert all(s["has_uploaded"] for s in data["upload_statuses"])


async def test_partial_upload_one_person(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    await upload_csv(client, alice_id, SHARED_CSV, auth=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", auth=cookies
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
        "/api/v1/reconciliation?year=2026&month=3", auth=cookies
    )
    assert response.status_code == 200

    data = response.json()
    assert data["transaction_count"] == 0
    assert data["total_household_spending"] == pytest.approx(0.0)
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
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=2", auth=cookies
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
    await upload_csv(client, alice_id, csv_jan, auth=cookies)
    await upload_csv(client, alice_id, csv_feb, auth=cookies)

    response = await client.get(
        "/api/v1/reconciliation?start_date=2026-01-01&end_date=2026-02-28",
        auth=cookies,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["start_date"] == "2026-01-01"
    assert data["end_date"] == "2026-02-28"
    assert data["transaction_count"] == 2
    assert data["total_household_spending"] == pytest.approx(160.0)
    # Multi-month range → year/month are None, is_finalized is None
    assert data["year"] is None
    assert data["month"] is None
    assert data["is_finalized"] is None


async def test_mixed_params_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1&start_date=2026-01-01&end_date=2026-01-31",
        auth=cookies,
    )
    assert response.status_code == 422


async def test_partial_range_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get(
        "/api/v1/reconciliation?start_date=2026-01-01", auth=cookies
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
    await upload_csv(client, alice_id, csv, auth=cookies)

    # Personal scope: every row where Alice's share is positive — her half
    # of the shared restaurant and her own coffee.
    response = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=personal&person_id={alice_id}",
        auth=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_count"] == 1  # the 50/50 restaurant enters settlement
    assert {t["merchant"] for t in data["transactions"]} == {"Restaurant", "Coffee"}


async def test_reconciliation_all_scope(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Restaurant,Dining Out,Chase,REST,,"-100.00",shared\n'
        '2026-01-16,Coffee,Dining Out,Chase,COFFEE,,"-5.00",\n'
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=all&person_id={alice_id}",
        auth=cookies,
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
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()
    # Default household scope: only shared restaurant
    assert len(data["transactions"]) == 1


async def _make_bike_row_a_personal_split(
    client: AsyncClient, alice_id: str, cookies: dict[str, str]
) -> None:
    """Turn the untagged bike row into a personal split (household stays false)."""
    recon = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=all&person_id={alice_id}",
        auth=cookies,
    )
    bike = next(t for t in recon.json()["transactions"] if t["merchant"] == "Bike Shop")
    assert bike["household"] is False
    resp = await client.patch(
        "/api/v1/transactions/splits",
        json={"splits": [{"transaction_id": bike["id"], "payer_percentage": 50}]},
        auth=cookies,
    )
    assert resp.status_code == 200


async def _assert_scope_all_settlement(
    client: AsyncClient,
    person_id: str,
    cookies: dict[str, str],
    *,
    amount: float,
    from_id: str,
    to_id: str,
) -> None:
    response = await client.get(
        f"/api/v1/reconciliation?year=2026&month=1&scope=all&person_id={person_id}",
        auth=cookies,
    )
    settlement = response.json()["settlement"]
    assert settlement["amount"] == pytest.approx(amount), person_id
    assert settlement["from_person_id"] == from_id
    assert settlement["to_person_id"] == to_id


async def test_settlement_relevant_rows_agree_across_surfaces(
    client: AsyncClient,
) -> None:
    """Spotted and personal-split rows (household=false) drive the same
    settlement number on Settle Up, both partners' reconciliation, and the
    adjustment export."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    alice_csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY,,"-100.00",shared\n'
        '2026-01-16,Parking Garage,Parking,Chase,PARKING,,"-40.00",bob\n'
        '2026-01-17,Bike Shop,Shopping,Chase,BIKE,,"-60.00",\n'
    )
    await upload_csv(client, alice_id, alice_csv, auth=cookies)
    bob_cookies = await login_as_bob(client)
    await upload_csv(client, bob_id, SHARED_CSV_BOB, auth=bob_cookies)

    await _make_bike_row_a_personal_split(client, alice_id, cookies)

    # Bob owes Alice: 50 (shared) + 40 (spotted) + 30 (personal split)
    # minus 20 (Bob's shared upload) = 100
    settle_up = await client.get(
        "/api/v1/settle-up", params={"year": 2026, "month": 1}, auth=cookies
    )
    data = settle_up.json()
    jan = next(m for m in data["months"] if (m["year"], m["month"]) == (2026, 1))
    assert jan["charged"]["amount"] == pytest.approx(100.0)
    assert jan["charged"]["from_person_id"] == bob_id
    assert jan["charged"]["to_person_id"] == alice_id
    splits_by_payer = {ps["payer_person_id"]: ps for ps in data["payer_splits"]}
    assert splits_by_payer[alice_id]["transaction_count"] == 3
    assert splits_by_payer[alice_id]["fronted"] == pytest.approx(200.0)

    # Both partners see the identical settlement under scope=all
    for person_id, person_cookies in ((alice_id, cookies), (bob_id, bob_cookies)):
        await _assert_scope_all_settlement(
            client,
            person_id,
            person_cookies,
            amount=100.0,
            from_id=bob_id,
            to_id=alice_id,
        )

    # The adjustment export covers the spotted and personal-split rows
    await client.patch(
        f"/api/v1/persons/{alice_id}",
        json={"adjustment_account": "Alice Adjustments"},
        auth=cookies,
    )
    preview = await client.get(
        f"/api/v1/persons/{alice_id}/adjustments/2026/1", auth=cookies
    )
    assert preview.status_code == 200
    merchants = {a["merchant"] for a in preview.json()["adjustments"]}
    assert "Parking Garage" in merchants
    assert "Bike Shop" in merchants
