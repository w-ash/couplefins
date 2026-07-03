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
    await upload_csv(client, alice_id, SPLIT_CSV, cookies=cookies)

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
        cookies=cookies,
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
        cookies=cookies,
    )
    data = settle_up.json()
    assert data["net_position"] is None
    assert data["remaining_balance"] == pytest.approx(0.0)
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
        cookies=cookies,
    )
    assert second.status_code == 422


async def test_candidates_returns_list(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/settlements/candidates",
        params={"year": 2026, "month": 3, "amount": 100.0},
        cookies=cookies,
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
