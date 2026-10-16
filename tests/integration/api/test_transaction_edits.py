import json
import uuid

from httpx import AsyncClient
from sqlalchemy import text

from src.infrastructure.persistence.database.db_connection import _get_engine
from tests.integration.api._joint import (
    Couple,
    couple_with_joint_exports,
    january,
    mark_joint,
)
from tests.integration.conftest import setup_and_login, upload_csv

SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    '2026-01-15,Restaurant,Restaurants & Bars,Chase,RESTAURANT,,"-80.00","shared,s50"\n'
)


async def _setup_transaction(
    client: AsyncClient,
) -> tuple[str, dict, dict[str, str]]:
    """Upload CSV and return (person_id, transaction dict, cookies)."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, SHARED_CSV, auth=cookies)

    resp = await client.get("/api/v1/reconciliation?year=2026&month=1", auth=cookies)
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
        auth=cookies,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == tx_id
    assert len(body["edits"]) == 1
    assert body["edits"][0]["field_name"] == "category"
    assert body["edits"][0]["old_value"] == "Restaurants & Bars"
    assert body["edits"][0]["new_value"] == "Fast Food"


async def test_patch_date_sets_original_date(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    resp = await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"date": "2026-01-20"},
        auth=cookies,
    )
    assert resp.status_code == 200

    # Verify original_date is set on the transaction
    recon = await client.get("/api/v1/reconciliation?year=2026&month=1", auth=cookies)
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
        auth=cookies,
    )

    resp = await client.patch(
        f"/api/v1/transactions/{tx['id']}",
        json={"category": "Fast Food"},
        auth=cookies,
    )
    assert resp.status_code == 409


async def test_patch_missing_transaction_returns_404(client: AsyncClient) -> None:
    _, _, cookies = await _setup_transaction(client)
    resp = await client.patch(
        "/api/v1/transactions/00000000-0000-0000-0000-000000000000",
        json={"category": "Fast Food"},
        auth=cookies,
    )
    assert resp.status_code == 404


async def test_get_edits_returns_history(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    # Make an edit
    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        auth=cookies,
    )

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", auth=cookies)
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_event"] is not None
    edits = body["edits"]
    assert len(edits) == 1
    assert edits[0]["field_name"] == "category"


async def test_multiple_edits_accumulate(client: AsyncClient) -> None:
    _, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        auth=cookies,
    )
    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"amount": -99.00},
        auth=cookies,
    )

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", auth=cookies)
    assert resp.status_code == 200
    edits = resp.json()["edits"]
    assert len(edits) == 2
    field_names = {e["field_name"] for e in edits}
    assert field_names == {"category", "amount"}


async def test_edit_carries_person_attribution(client: AsyncClient) -> None:
    alice_id, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    resp = await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        auth=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["edits"][0]["edited_by_person_id"] == alice_id

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", auth=cookies)
    assert resp.status_code == 200
    assert resp.json()["edits"][0]["edited_by_person_id"] == alice_id


async def test_get_edits_returns_import_event(client: AsyncClient) -> None:
    alice_id, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", auth=cookies)
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_event"] is not None
    assert body["import_event"]["person_id"] == alice_id
    assert body["import_event"]["imported_at"] is not None


async def test_full_lifecycle_import_and_edits(client: AsyncClient) -> None:
    alice_id, tx, cookies = await _setup_transaction(client)
    tx_id = tx["id"]

    await client.patch(
        f"/api/v1/transactions/{tx_id}",
        json={"category": "Fast Food"},
        auth=cookies,
    )

    resp = await client.get(f"/api/v1/transactions/{tx_id}/edits", auth=cookies)
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_event"]["person_id"] == alice_id
    assert len(body["edits"]) == 1
    assert body["edits"][0]["edited_by_person_id"] == alice_id


# --- Joint rows: owner shares and depositor (US-JOINT-1, US-JOINT-2) ---


async def _joint_rows(client: AsyncClient) -> tuple[Couple, dict[str, dict]]:
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)
    recon = await january(client, couple.alice)
    return couple, {tx["merchant"]: tx for tx in recon["transactions"]}


async def test_owner_shares_and_depositor_edit_a_joint_row(
    client: AsyncClient,
) -> None:
    couple, rows = await _joint_rows(client)
    grocery = rows["Grocery Store"]["id"]
    deposit = rows["Transfer From Alice"]["id"]

    shares = await client.patch(
        f"/api/v1/transactions/{grocery}",
        json={"owner_shares": {couple.alice_id: 60, couple.bob_id: 40}},
        auth=couple.bob,
    )
    depositor = await client.patch(
        "/api/v1/transactions/bulk-update",
        json={"transaction_ids": [deposit], "depositor_person_id": couple.bob_id},
        auth=couple.bob,
    )

    assert shares.status_code == 200
    [edit] = shares.json()["edits"]
    assert edit["field_name"] == "owner_shares"
    assert depositor.status_code == 200
    after = {
        tx["id"]: tx for tx in (await january(client, couple.alice))["transactions"]
    }
    assert after[grocery]["shares"] == {couple.alice_id: 60, couple.bob_id: 40}
    assert after[deposit]["depositor_person_id"] == couple.bob_id


async def test_null_resets_owner_shares_and_omitted_keeps_them(
    client: AsyncClient,
) -> None:
    couple, rows = await _joint_rows(client)
    hardware = rows["Hardware Store"]["id"]
    assert rows["Hardware Store"]["owner_shares"] is not None

    kept = await client.patch(
        f"/api/v1/transactions/{hardware}", json={"notes": "paint"}, auth=couple.alice
    )
    after_kept = await january(client, couple.alice)
    reset = await client.patch(
        f"/api/v1/transactions/{hardware}",
        json={"owner_shares": None},
        auth=couple.alice,
    )

    assert (kept.status_code, reset.status_code) == (200, 200)
    by_id = {tx["id"]: tx for tx in after_kept["transactions"]}
    assert by_id[hardware]["owner_shares"] is not None
    after_reset = {
        tx["id"]: tx for tx in (await january(client, couple.alice))["transactions"]
    }
    assert after_reset[hardware]["owner_shares"] is None
    assert after_reset[hardware]["shares"] == {couple.alice_id: 50, couple.bob_id: 50}


async def test_joint_only_edits_are_rejected_on_a_personal_row(
    client: AsyncClient,
) -> None:
    couple, rows = await _joint_rows(client)
    dinner = rows["Restaurant"]["id"]

    shares = await client.patch(
        f"/api/v1/transactions/{dinner}",
        json={"owner_shares": {couple.alice_id: 50, couple.bob_id: 50}},
        auth=couple.alice,
    )
    depositor = await client.patch(
        f"/api/v1/transactions/{dinner}",
        json={"depositor_person_id": couple.alice_id},
        auth=couple.alice,
    )

    assert (shares.status_code, depositor.status_code) == (422, 422)


async def test_a_joint_row_rejects_a_payer_split_and_personal(
    client: AsyncClient,
) -> None:
    couple, rows = await _joint_rows(client)
    grocery = rows["Grocery Store"]["id"]

    split = await client.patch(
        f"/api/v1/transactions/{grocery}",
        json={"payer_percentage": 50},
        auth=couple.alice,
    )
    personal = await client.patch(
        f"/api/v1/transactions/{grocery}", json={"household": False}, auth=couple.alice
    )

    assert (split.status_code, personal.status_code) == (422, 422)


async def test_owner_shares_must_sum_to_100(client: AsyncClient) -> None:
    couple, rows = await _joint_rows(client)

    response = await client.patch(
        f"/api/v1/transactions/{rows['Grocery Store']['id']}",
        json={"owner_shares": {couple.alice_id: 60, couple.bob_id: 30}},
        auth=couple.alice,
    )

    assert response.status_code == 422


async def test_a_row_naming_persons_outside_the_couple_lists_with_no_shares(
    client: AsyncClient,
) -> None:
    """Stale owner shares log a warning; the list still serves (no 500)."""
    couple, rows = await _joint_rows(client)
    grocery = rows["Grocery Store"]["id"]
    stale = json.dumps({couple.alice_id: 50, str(uuid.uuid4()): 50})
    async with _get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE transactions SET owner_shares = CAST(:s AS jsonb) WHERE id = :i"
            ),
            {"s": stale, "i": grocery},
        )

    listed = {
        tx["id"]: tx for tx in (await january(client, couple.alice))["transactions"]
    }

    assert (listed[grocery]["shares"], listed[grocery]["share_amounts"]) == ({}, {})
    assert listed[rows["Hardware Store"]["id"]]["shares"] != {}
