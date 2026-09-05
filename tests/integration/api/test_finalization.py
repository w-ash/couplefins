from httpx import AsyncClient

from tests.integration.conftest import setup_and_login


async def test_finalize_creates_period(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1, "notes": "Reviewed together"},
        auth=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None
    assert data["notes"] == "Reviewed together"


async def test_finalize_already_finalized_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 2},
        auth=cookies,
    )
    response = await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 2},
        auth=cookies,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unfinalize_period(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 3},
        auth=cookies,
    )
    response = await client.post(
        "/api/v1/reconciliation/unfinalize",
        json={"year": 2026, "month": 3},
        auth=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is False
    assert data["finalized_at"] is None


async def test_unfinalize_not_finalized_returns_422(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.post(
        "/api/v1/reconciliation/unfinalize",
        json={"year": 2026, "month": 4},
        auth=cookies,
    )
    assert response.status_code == 422


async def test_period_status_not_finalized(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/reconciliation/period-status?year=2026&month=5",
        auth=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is False
    assert data["finalized_at"] is None


async def test_period_status_finalized(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 6, "notes": "Done"},
        auth=cookies,
    )
    response = await client.get(
        "/api/v1/reconciliation/period-status?year=2026&month=6",
        auth=cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["notes"] == "Done"


async def test_upload_to_finalized_month_returns_409(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1},
        auth=cookies,
    )

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Dining Out,Chase,,,-50.00,shared\n"
    )
    import io

    response = await client.post(
        "/api/v1/uploads/",
        data={"person_id": alice_id},
        files={"file": ("test.csv", io.BytesIO(csv.encode()), "text/csv")},
        auth=cookies,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERIOD_FINALIZED"


async def test_reconciliation_includes_finalization_status(
    client: AsyncClient,
) -> None:
    _, cookies = await setup_and_login(client)
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 7, "notes": "July done"},
        auth=cookies,
    )
    response = await client.get(
        "/api/v1/reconciliation?year=2026&month=7", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None


async def test_dashboard_includes_finalization_status(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 8},
        auth=cookies,
    )
    response = await client.get("/api/v1/dashboard?year=2026&month=8", auth=cookies)
    assert response.status_code == 200
    data = response.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None


async def test_finalized_month_locks_budgets_but_not_settlement_records(
    client: AsyncClient,
) -> None:
    """Lock Month freezes transactions and budgets. Settlement records post
    against the running ledger and stay allowed on locked months (v1.7.5)."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    bob_id = persons[1]["id"]

    groups = await client.get("/api/v1/category-groups", auth=cookies)
    # The first seeded group is Income, which carries no budget.
    group_id = next(g["id"] for g in groups.json() if g["kind"] == "expense")

    finalize = await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1, "notes": ""},
        auth=cookies,
    )
    assert finalize.status_code == 200

    record = await client.post(
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
    assert record.status_code == 201

    budget = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )
    assert budget.status_code == 409
