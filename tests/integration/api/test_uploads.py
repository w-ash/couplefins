import io
import json

from httpx import AsyncClient

from tests.integration.conftest import setup_couple

VALID_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,\n"
)


async def test_upload_csv_full_flow(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    person_id = persons[0]["id"]

    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["new_count"] == 2
    assert data["updated_count"] == 0
    assert data["skipped_count"] == 0
    assert data["filename"] == "test.csv"


async def test_upload_csv_idempotent_reupload(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    person_id = persons[0]["id"]

    # First upload
    await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )

    # Second upload of same CSV → all unchanged
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["new_count"] == 0
    assert data["updated_count"] == 0
    assert data["skipped_count"] == 2


async def test_upload_csv_with_accepted_changes(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    person_id = persons[0]["id"]

    # First upload
    await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )

    # Preview with changed merchant
    changed_csv = VALID_CSV.replace("Grocery Store", "Updated Grocery")
    preview_resp = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(changed_csv.encode()), "text/csv")},
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
    )
    assert response.status_code == 201
    data = response.json()
    assert data["updated_count"] == 1
    assert data["skipped_count"] == 1  # Gas Station unchanged


async def test_upload_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": fake_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 404


async def test_preview_csv_full_flow(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    person_id = persons[0]["id"]

    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["new_transactions"]) == 2
    assert data["unchanged_count"] == 0
    assert data["changed_transactions"] == []
    assert data["new_transactions"][0]["merchant"] == "Grocery Store"
    assert data["new_transactions"][0]["is_shared"] is True


async def test_preview_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": fake_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 404
