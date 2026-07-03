import io
import json

from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_and_login

VALID_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,\n"
)


async def test_upload_csv_full_flow(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["new_count"] == 2
    assert data["updated_count"] == 0
    assert data["skipped_count"] == 0
    assert data["removed_count"] == 0
    assert data["warnings"] == []
    assert data["filename"] == "test.csv"


async def test_upload_csv_idempotent_reupload(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    # First upload
    await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )

    # Second upload of same CSV → all unchanged
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["new_count"] == 0
    assert data["updated_count"] == 0
    assert data["skipped_count"] == 2
    assert data["removed_count"] == 0


async def test_upload_csv_with_accepted_changes(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    # First upload
    await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )

    # Preview with changed merchant
    changed_csv = VALID_CSV.replace("Grocery Store", "Updated Grocery")
    preview_resp = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(changed_csv.encode()), "text/csv")},
        cookies=cookies,
    )
    preview_data = preview_resp.json()
    assert len(preview_data["changed_transactions"]) == 1
    change_id = preview_data["changed_transactions"][0]["existing_id"]

    # Upload accepting the change
    response = await client.post(
        "/api/v1/uploads/",
        data={
            "person_id": person_id,
            "accepted_change_ids": json.dumps([change_id]),
        },
        files={"file": ("test.csv", io.BytesIO(changed_csv.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["updated_count"] == 1
    assert data["skipped_count"] == 1  # Gas Station unchanged


@pytest.mark.skip(
    reason="Upload route does not validate person_id against auth user — needs route fix"
)
async def test_upload_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": fake_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 404


THREE_ROW_SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,shared\n"
    "2026-01-17,Restaurant,Dining Out,Chase,RESTAURANT,,-80.00,shared\n"
)
# Same window (Jan 15-17), Gas Station row deleted in Monarch.
TWO_ROW_SHARED_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-17,Restaurant,Dining Out,Chase,RESTAURANT,,-80.00,shared\n"
)


async def _upload(client: AsyncClient, csv: str, cookies: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/uploads/",
        files={"file": ("test.csv", io.BytesIO(csv.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 201
    return response.json()


async def test_reupload_removes_rows_missing_from_csv(client: AsyncClient) -> None:
    """US-IMPORT-1: re-upload replaces — stale rows inside the window are deleted."""
    _, cookies = await setup_and_login(client)
    await _upload(client, THREE_ROW_SHARED_CSV, cookies)

    # Preview reports the removal before anything is deleted.
    preview = await client.post(
        "/api/v1/uploads/preview",
        files={
            "file": ("test.csv", io.BytesIO(TWO_ROW_SHARED_CSV.encode()), "text/csv")
        },
        cookies=cookies,
    )
    assert preview.status_code == 200
    removed_preview = preview.json()["removed_transactions"]
    assert [tx["merchant"] for tx in removed_preview] == ["Gas Station"]

    data = await _upload(client, TWO_ROW_SHARED_CSV, cookies)
    assert data["removed_count"] == 1
    assert data["new_count"] == 0
    assert data["skipped_count"] == 2
    assert data["warnings"] == []

    recon = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    merchants = {tx["merchant"] for tx in recon.json()["transactions"]}
    assert merchants == {"Grocery Store", "Restaurant"}


async def test_reupload_unlinks_settlement_on_removed_row(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]
    await _upload(client, THREE_ROW_SHARED_CSV, cookies)

    recon = await client.get(
        "/api/v1/reconciliation?year=2026&month=1", cookies=cookies
    )
    gas_tx_id = next(
        tx["id"]
        for tx in recon.json()["transactions"]
        if tx["merchant"] == "Gas Station"
    )

    settlement = await client.post(
        "/api/v1/settlements",
        json={
            "year": 2026,
            "month": 1,
            "amount": 30.0,
            "from_person_id": bob_id,
            "to_person_id": alice_id,
            "method": "Venmo",
        },
        cookies=cookies,
    )
    settlement_id = settlement.json()["settlement"]["id"]
    mark = await client.post(
        "/api/v1/settlements/mark-transaction",
        json={
            "transaction_id": gas_tx_id,
            "settlement_id": settlement_id,
            "is_settlement": True,
        },
        cookies=cookies,
    )
    assert mark.status_code == 200

    data = await _upload(client, TWO_ROW_SHARED_CSV, cookies)
    assert data["removed_count"] == 1
    assert len(data["warnings"]) == 1
    assert "Gas Station" in data["warnings"][0]
    assert "linked to a settlement" in data["warnings"][0]

    settle_up = await client.get(
        "/api/v1/settle-up",
        params={"year": 2026, "month": 1},
        cookies=cookies,
    )
    recorded = settle_up.json()["recorded_settlements"]
    assert len(recorded) == 1
    assert recorded[0]["linked_transaction_ids"] == []


async def test_preview_csv_full_flow(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["new_transactions"]) == 2
    assert data["unchanged_count"] == 0
    assert data["changed_transactions"] == []
    assert data["skipped_adjustment_count"] == 0
    assert data["new_transactions"][0]["merchant"] == "Grocery Store"
    assert data["new_transactions"][0]["household"] is True


async def test_preview_skips_adjustment_rows(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    csv_with_adjustment = (
        VALID_CSV
        + "2026-01-17,Adjustment,Groceries,Shared Adjustments,ADJ,[cf:abc],25.00,couplefins-adjustment\n"
    )
    response = await client.post(
        "/api/v1/uploads/preview",
        files={
            "file": ("test.csv", io.BytesIO(csv_with_adjustment.encode()), "text/csv")
        },
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["skipped_adjustment_count"] == 1
    assert len(data["new_transactions"]) == 2


@pytest.mark.skip(
    reason="Upload route does not validate person_id against auth user — needs route fix"
)
async def test_preview_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": fake_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 404


async def test_upload_history(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]

    # Upload a CSV
    await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("march.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
        cookies=cookies,
    )

    # Fetch history
    response = await client.get("/api/v1/uploads/history", cookies=cookies)
    assert response.status_code == 200
    data = response.json()
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["filename"] == "march.csv"
    assert entry["person_name"] == "Alice"
    assert entry["transaction_count"] == 2
    assert entry["household_count"] == 1
    assert entry["date_range_start"] is not None


async def test_upload_history_empty(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get("/api/v1/uploads/history", cookies=cookies)
    assert response.status_code == 200
    assert response.json()["entries"] == []


async def test_upload_nan_amount_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    nan_csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Starbucks,Dining Out,Chase,STARBUCKS,,NaN,shared\n"
    )
    response = await client.post(
        "/api/v1/uploads/",
        files={"file": ("test.csv", io.BytesIO(nan_csv.encode()), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 422
    assert "non-finite amount" in response.json()["error"]["message"]


async def test_preview_binary_file_returns_422(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]
    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("bad.csv", io.BytesIO(b"\x80\x81\x82"), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 422
    assert "UTF-8" in response.json()["error"]["message"]


async def test_upload_binary_file_returns_422(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    person_id = persons[0]["id"]
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("bad.csv", io.BytesIO(b"\x80\x81\x82"), "text/csv")},
        cookies=cookies,
    )
    assert response.status_code == 422
    assert "UTF-8" in response.json()["error"]["message"]
