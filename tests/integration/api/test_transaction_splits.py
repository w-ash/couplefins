from httpx import AsyncClient

from tests.integration.conftest import setup_couple, upload_csv

SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Restaurant,Dining Out,Chase,RESTAURANT,,"-80.00","shared,s50"\n'
    '2026-01-16,Grocery Store,Groceries,Chase,GROCERY,,"-60.00",shared\n'
)


async def _setup_transactions(client: AsyncClient) -> tuple[str, list[dict]]:
    """Upload CSV and return (person_id, transactions from reconciliation)."""
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, SHARED_CSV)

    resp = await client.get("/api/v1/reconciliation?year=2026&month=1")
    assert resp.status_code == 200
    txs = resp.json()["transactions"]
    assert len(txs) == 2
    return alice_id, txs


async def test_update_single_split(client: AsyncClient) -> None:
    _, txs = await _setup_transactions(client)
    tx_id = txs[0]["id"]

    response = await client.patch(
        "/api/v1/transactions/splits",
        json={"splits": [{"transaction_id": tx_id, "payer_percentage": 70}]},
    )
    assert response.status_code == 200
    assert response.json()["updated_count"] == 1

    # Verify the change persisted
    resp = await client.get("/api/v1/reconciliation?year=2026&month=1")
    updated_tx = next(t for t in resp.json()["transactions"] if t["id"] == tx_id)
    assert updated_tx["payer_percentage"] == 70


async def test_update_bulk_splits(client: AsyncClient) -> None:
    _, txs = await _setup_transactions(client)

    response = await client.patch(
        "/api/v1/transactions/splits",
        json={
            "splits": [
                {"transaction_id": txs[0]["id"], "payer_percentage": 60},
                {"transaction_id": txs[1]["id"], "payer_percentage": 80},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["updated_count"] == 2


async def test_update_split_on_finalized_month_returns_409(
    client: AsyncClient,
) -> None:
    _, txs = await _setup_transactions(client)

    await client.post(
        "/api/v1/reconciliation/finalize", json={"year": 2026, "month": 1}
    )

    response = await client.patch(
        "/api/v1/transactions/splits",
        json={"splits": [{"transaction_id": txs[0]["id"], "payer_percentage": 70}]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERIOD_FINALIZED"


async def test_update_split_missing_transaction_returns_404(
    client: AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/transactions/splits",
        json={
            "splits": [
                {
                    "transaction_id": "00000000-0000-0000-0000-000000000000",
                    "payer_percentage": 70,
                }
            ]
        },
    )
    assert response.status_code == 404


async def test_update_split_invalid_percentage_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/transactions/splits",
        json={
            "splits": [
                {
                    "transaction_id": "00000000-0000-0000-0000-000000000000",
                    "payer_percentage": 150,
                }
            ]
        },
    )
    assert response.status_code == 422


async def test_update_split_empty_list_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/transactions/splits",
        json={"splits": []},
    )
    assert response.status_code == 422


async def test_settlement_updates_after_split_change(client: AsyncClient) -> None:
    """Changing a split should affect the reconciliation settlement."""
    _, txs = await _setup_transactions(client)

    resp_before = await client.get("/api/v1/reconciliation?year=2026&month=1")
    settlement_before = resp_before.json()["settlement"]

    # Change the restaurant from 50/50 to 100/0 (payer covers everything)
    restaurant_tx = next(t for t in txs if t["merchant"] == "Restaurant")
    await client.patch(
        "/api/v1/transactions/splits",
        json={
            "splits": [{"transaction_id": restaurant_tx["id"], "payer_percentage": 100}]
        },
    )

    resp_after = await client.get("/api/v1/reconciliation?year=2026&month=1")
    settlement_after = resp_after.json()["settlement"]

    # Settlement should have changed
    assert settlement_before["amount"] != settlement_after["amount"]
