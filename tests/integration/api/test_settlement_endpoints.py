from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_and_login, upload_csv

SPLIT_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
)


async def test_waive_persists_remaining_balance(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    # Alice paid $100 at 50/50 → Bob owes Alice $50.
    response = await client.post(
        "/api/v1/settlements/waive",
        json={
            "year": 2026,
            "month": 1,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "notes": "Forgiven",
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
    assert data["outstanding"] is None
    assert data["ledger_months"][0]["status"] == "settled"
    assert data["ledger_months"][0]["remaining"] == pytest.approx(0.0)
    waiver = data["recorded_settlements"][0]
    assert waiver["is_waived"] is True
    assert waiver["amount"] == pytest.approx(50.0)

    # The balance is settled now — a second waive has nothing to forgive.
    second = await client.post(
        "/api/v1/settlements/waive",
        json={
            "year": 2026,
            "month": 1,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
        },
        auth=cookies,
    )
    assert second.status_code == 422


async def test_waive_without_annotation(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await upload_csv(client, alice_id, SPLIT_CSV, auth=cookies)

    response = await client.post(
        "/api/v1/settlements/waive",
        json={"from_person_id": bob_id, "to_person_id": alice_id},
        auth=cookies,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["settlement"]["amount"] == pytest.approx(50.0)
    assert body["settlement"]["year"] is None
    assert body["settlement"]["month"] is None


async def test_multi_month_catch_up_settles_both_months(client: AsyncClient) -> None:
    """One payment without a month annotation clears two open months FIFO."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        '2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,"-100.00",shared\n'
        '2026-02-10,Restaurant,Dining Out,Chase,RESTAURANT,,"-60.00",shared\n'
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    # Bob owes Alice $50 (Jan) + $30 (Feb) — one catch-up payment, no month.
    record = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 80.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
        },
        auth=cookies,
    )
    assert record.status_code == 201
    assert record.json()["settlement"]["year"] is None

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 2},
        auth=cookies,
    )
    data = settle_up.json()
    assert data["outstanding"] is None
    assert data["outstanding_span"] is None
    statuses = {(m["year"], m["month"]): m["status"] for m in data["ledger_months"]}
    assert statuses == {(2026, 1): "settled", (2026, 2): "settled"}
    payment = data["all_settlements"][0]
    assert payment["covered"] == [
        {"year": 2026, "month": 1, "amount": 50.0},
        {"year": 2026, "month": 2, "amount": 30.0},
    ]
    assert payment["unapplied"] == pytest.approx(0.0)


async def test_record_half_set_annotation_is_422_not_500(
    client: AsyncClient,
) -> None:
    """A year without its month is bad input — reject at the boundary (422),
    not a bare ValueError surfacing as a 500."""
    persons, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/settlements",
        json={
            "amount": 50.0,
            "from_person_id": persons[1]["id"],
            "to_person_id": persons[0]["id"],
            "method": "Venmo",
            "year": 2026,
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
            "year": 2026,
            "month": 1,
            "amount": 49.999999999999996,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
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
    assert data["outstanding"] is None
    assert data["ledger_months"][0]["remaining"] == pytest.approx(0.0)


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
            "year": 2026,
            "month": 1,
            "amount": 50.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
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
