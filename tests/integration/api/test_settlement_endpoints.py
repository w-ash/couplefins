from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_and_login, upload_csv

SPLIT_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
)


def _month(data: dict, year: int, month: int) -> dict:
    return next(m for m in data["months"] if (m["year"], m["month"]) == (year, month))


def _year(data: dict, year: int) -> dict:
    return next(y for y in data["years"] if y["year"] == year)


async def test_waive_persists_remaining_balance(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    # Alice paid $100 at 50/50 → Bob owes Alice $50.
    response = await client.post(
        "/api/v1/settlements/waive",
        json={
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "notes": "Waived",
        },
        auth=cookies,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["settlement"]["amount"] == pytest.approx(50.0)
    assert body["settlement"]["is_waived"] is True
    # Bob hasn't uploaded — the waived amount may be premature.
    assert any("No upload from Bob" in w for w in body["warnings"])

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 1},
        auth=cookies,
    )
    data = settle_up.json()
    jan = _month(data, 2026, 1)
    assert jan["status"] == "settled"
    assert jan["balance"] is None
    assert _year(data, 2026)["balance"] is None
    waiver = data["settlements"][0]
    assert waiver["is_waived"] is True
    assert waiver["amount"] == pytest.approx(50.0)
    # The waiver's portion pins it to the month it relieved.
    assert waiver["portions"] == [{"year": 2026, "month": 1, "amount": 50.0}]

    # The balance is settled now — a second waive has nothing to relieve.
    second = await client.post(
        "/api/v1/settlements/waive",
        json={"from_person_id": bob_id, "to_person_id": alice_id},
        auth=cookies,
    )
    assert second.status_code == 422


async def test_multi_month_catch_up_settles_both_months(client: AsyncClient) -> None:
    """One payment covering two months stores one portion per month."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
        '2026-02-10,Restaurant,Dining Out,Chase,RESTAURANT,,"-60.00",shared\n'
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    # Bob owes Alice $50 (Jan) + $30 (Feb) — one catch-up lump.
    record = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 80.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
            "covered_months": [
                {"year": 2026, "month": 1},
                {"year": 2026, "month": 2},
            ],
        },
        auth=cookies,
    )
    assert record.status_code == 201

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 2},
        auth=cookies,
    )
    data = settle_up.json()
    statuses = {(m["year"], m["month"]): m["status"] for m in data["months"]}
    assert statuses == {(2026, 1): "settled", (2026, 2): "settled"}
    assert _year(data, 2026)["balance"] is None
    payment = data["settlements"][0]
    assert payment["portions"] == [
        {"year": 2026, "month": 1, "amount": 50.0},
        {"year": 2026, "month": 2, "amount": 30.0},
    ]


async def test_month_paid_past_charges_swings_and_flags_direction(
    client: AsyncClient,
) -> None:
    """A month paid past its charges shows its balance the other way, and
    the row is flagged as running against the year's direction."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
        '2026-02-10,Restaurant,Dining Out,Chase,RESTAURANT,,"-300.00",shared\n'
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    # Bob owes Alice $50 (Jan) + $150 (Feb). He pays $80 covering January
    # only — January swings to Alice-owes-Bob $30 while the year still runs
    # Bob-owes-Alice $120.
    record = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 80.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
            "covered_months": [{"year": 2026, "month": 1}],
        },
        auth=cookies,
    )
    assert record.status_code == 201

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 1},
        auth=cookies,
    )
    data = settle_up.json()
    jan = _month(data, 2026, 1)
    assert jan["status"] == "partially_settled"
    assert jan["balance"]["amount"] == pytest.approx(30.0)
    assert jan["balance"]["from_person_id"] == alice_id
    assert jan["runs_against_year"] is True
    feb = _month(data, 2026, 2)
    assert feb["balance"]["amount"] == pytest.approx(150.0)
    assert feb["runs_against_year"] is False
    year = _year(data, 2026)
    assert year["balance"]["amount"] == pytest.approx(120.0)
    assert year["balance"]["from_person_id"] == bob_id
    assert year["charged"]["amount"] == pytest.approx(200.0)
    assert year["paid"]["amount"] == pytest.approx(80.0)


async def test_record_invalid_covered_month_is_422_not_500(
    client: AsyncClient,
) -> None:
    """An out-of-range covered month is bad input — reject at the boundary
    (422), not a bare ValueError surfacing as a 500."""
    persons, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 50.0,
            "from_person_id": persons[1]["id"],
            "to_person_id": persons[0]["id"],
            "method": "Venmo",
            "covered_months": [{"year": 2026, "month": 13}],
        },
        auth=cookies,
    )
    assert response.status_code == 422


async def test_candidates_returns_list(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/settlements/candidates",
        params={"year": 2026, "month": 3, "amount": 100.0},
        auth=cookies,
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


async def test_recording_the_gross_nets_month_to_exactly_zero(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    # Bob owes Alice exactly $50 — pay with a float-dusty amount.
    record = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 49.999999999999996,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
            "covered_months": [{"year": 2026, "month": 1}],
        },
        auth=cookies,
    )
    assert record.status_code == 201
    assert record.json()["settlement"]["amount"] == pytest.approx(50.0)

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 1},
        auth=cookies,
    )
    data = settle_up.json()
    jan = _month(data, 2026, 1)
    assert jan["balance"] is None
    assert jan["status"] == "settled"
    assert _year(data, 2026)["balance"] is None


async def test_deleting_a_settlement_removes_its_portions(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    record = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 50.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
            "covered_months": [{"year": 2026, "month": 1}],
        },
        auth=cookies,
    )
    settlement_id = record.json()["settlement"]["id"]

    delete = await client.delete(f"/api/v1/settlements/{settlement_id}", auth=cookies)
    assert delete.status_code == 200

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 1},
        auth=cookies,
    )
    data = settle_up.json()
    assert data["settlements"] == []
    jan = _month(data, 2026, 1)
    assert jan["balance"]["amount"] == pytest.approx(50.0)
    assert jan["status"] == "carried_forward"


async def test_mark_transaction_link_hygiene(client: AsyncClient) -> None:
    """Double-link returns a clean 422 (not an IntegrityError 500); unmark
    deletes the link so the transaction can be re-linked."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    recon = await client.get("/api/v1/reconciliation?year=2026&month=1", auth=cookies)
    tx_id = recon.json()["transactions"][0]["id"]

    settlement = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 50.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
            "covered_months": [{"year": 2026, "month": 1}],
        },
        auth=cookies,
    )
    settlement_id = settlement.json()["settlement"]["id"]

    def mark_body(settle: bool) -> dict:
        body: dict = {"transaction_id": tx_id, "is_settlement": settle}
        if settle:
            body["settlement_id"] = settlement_id
        return body

    first = await client.post(
        "/api/v1/settlements/mark-transaction",
        json=mark_body(True),
        auth=cookies,
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/settlements/mark-transaction",
        json=mark_body(True),
        auth=cookies,
    )
    assert second.status_code == 422
    assert "already linked" in second.json()["error"]["message"]

    unmark = await client.post(
        "/api/v1/settlements/mark-transaction",
        json=mark_body(False),
        auth=cookies,
    )
    assert unmark.status_code == 200

    relink = await client.post(
        "/api/v1/settlements/mark-transaction",
        json=mark_body(True),
        auth=cookies,
    )
    assert relink.status_code == 200
