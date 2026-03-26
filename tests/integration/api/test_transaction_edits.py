from httpx import AsyncClient

from tests.integration.conftest import setup_and_login, upload_csv

SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Restaurant,Dining Out,Chase,RESTAURANT,,"-80.00","shared,s50"\n'
)


async def _setup_transaction(
    client: AsyncClient,
) -> tuple[str, dict, dict[str, str]]:
    """Upload CSV and return (person_id, transaction dict, cookies)."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, SHARED_CSV, cookies=cookies)

    resp = await client.get("/api/v1/reconciliation?year=2026&month=1", cookies=cookies)
    assert resp.status_code == 200
    txs = resp.json()["transactions"]
    assert len(txs) == 1
    return alice_id, txs[0], cookies


async def test_patch_updates_category(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    resp = await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == tx_id
    assert len(body["edits"]) == 1
    assert body["edits"][0]["field_name"] == "category"
    assert body["edits"][0]["old_value"] == "Dining Out"
    assert body["edits"][0]["new_value"] == "Fast Food"


async def test_patch_date_sets_original_date(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    resp = await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"date": "2026-01-20"},
        cookies=cookies,
    )
    assert resp.status_code == 200

    # Verify original_date is set on the transaction
    recon = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    updated_tx = next(
        (t for t in recon.json()["transactions"] if t["id"] == tx_id), None
    )
    assert updated_tx is not None
    assert updated_tx["original_date"] == "2026-01-15"
    assert updated_tx["date"] == "2026-01-20"


async def test_patch_finalized_month_returns_409(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)

    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1},
        cookies=cookies,
    )

    resp = await client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"category": "Fast Food"},
        cookies=cookies,
    )
    assert resp.status_code == 409


async def test_patch_missing_transaction_returns_404(client: AsyncClient) -> None:
    _, _, cookies = await _setup_transaction(client)
    resp = await client.patch(
        "/api/v1/transactions/00000000-0000-0000-0000-000000000000",
        json={"category": "Fast Food"},
        cookies=cookies,
    )
    assert resp.status_code == 404


async def test_get_edits_returns_history(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    # Make an edit
    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        cookies=cookies,
    )

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", cookies=cookies)
    assert resp.status_code == 200
    edits = resp.json()["edits"]
    assert len(edits) == 1
    assert edits[0]["field_name"] == "category"


async def test_multiple_edits_accumulate(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        cookies=cookies,
    )
    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"amount": -99.00},
        cookies=cookies,
    )

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", cookies=cookies)
    assert resp.status_code == 200
    edits = resp.json()["edits"]
    assert len(edits) == 2
    field_names = {e["field_name"] for e in edits}
    assert field_names == {"category", "amount"}
