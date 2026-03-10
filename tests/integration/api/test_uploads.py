import io

from httpx import AsyncClient

VALID_CSV = (
    "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
    "2026-01-15,Grocery Store,Groceries,Chase,GROCERY STORE,,-50.00,shared\n"
    "2026-01-16,Gas Station,Gas,Chase,GAS STATION,,-30.00,\n"
)


async def test_upload_csv_full_flow(client: AsyncClient) -> None:
    # Create a person first
    person_resp = await client.post("/api/v1/persons/", json={"name": "Alice"})
    person_id = person_resp.json()["id"]

    # Upload CSV
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": person_id, "year": "2026", "month": "1"},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_transactions"] == 2
    assert data["shared_count"] == 1
    assert data["personal_count"] == 1
    assert data["filename"] == "test.csv"
    assert data["period_year"] == 2026
    assert data["period_month"] == 1


async def test_upload_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": fake_id, "year": "2026", "month": "1"},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 404


async def test_preview_csv_full_flow(client: AsyncClient) -> None:
    person_resp = await client.post("/api/v1/persons/", json={"name": "Alice"})
    person_id = person_resp.json()["id"]

    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": person_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    assert data["shared_count"] == 1
    assert data["personal_count"] == 1
    assert len(data["transactions"]) == 2
    assert data["transactions"][0]["merchant"] == "Grocery Store"
    assert data["transactions"][0]["is_shared"] is True


async def test_preview_csv_unknown_person_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        "/api/v1/uploads/preview",
        data={"person_id": fake_id},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV.encode()), "text/csv")},
    )
    assert response.status_code == 404
