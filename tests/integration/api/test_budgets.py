from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_couple, upload_csv


async def test_budget_overview_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/budgets/overview?year=2026&month=1")
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert data["group_statuses"] == []
    assert data["budgets"] == []


async def test_create_budget(client: AsyncClient) -> None:
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}
    )
    group_id = group_resp.json()["id"]

    response = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["group_id"] == group_id
    assert data["monthly_amount"] == pytest.approx(500.0)
    assert data["effective_from"] == "2026-01-01"
    assert "id" in data


async def test_update_budget(client: AsyncClient) -> None:
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Home Expenses"}
    )
    group_id = group_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
    )
    budget_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/budgets/{budget_id}",
        json={"monthly_amount": 600.0},
    )
    assert response.status_code == 200
    assert response.json()["monthly_amount"] == pytest.approx(600.0)


async def test_delete_budget(client: AsyncClient) -> None:
    group_resp = await client.post("/api/v1/category-groups", json={"name": "Shopping"})
    group_id = group_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 300.0,
            "effective_from": "2026-01-01",
        },
    )
    budget_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/budgets/{budget_id}")
    assert response.status_code == 204


async def test_delete_nonexistent_budget_returns_404(client: AsyncClient) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/budgets/{fake_id}")
    assert response.status_code == 404


async def test_list_budgets(client: AsyncClient) -> None:
    group_resp = await client.post("/api/v1/category-groups", json={"name": "Health"})
    group_id = group_resp.json()["id"]

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 200.0,
            "effective_from": "2026-01-01",
        },
    )

    response = await client.get("/api/v1/budgets")
    assert response.status_code == 200
    budgets = response.json()
    assert len(budgets) >= 1
    assert any(b["group_id"] == group_id for b in budgets)


async def test_overview_with_budget_and_spending(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    alice_id = persons[0]["id"]

    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}
    )
    group_id = group_resp.json()["id"]

    await client.put(
        "/api/v1/category-mappings",
        json={"mappings": [{"category": "Dining Out", "group_id": group_id}]},
    )

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
    )

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Dining Out,Chase,,,-50.00,shared\n"
    )
    await upload_csv(client, alice_id, csv)

    response = await client.get("/api/v1/budgets/overview?year=2026&month=1")
    assert response.status_code == 200
    data = response.json()

    budgeted = [s for s in data["group_statuses"] if s["monthly_budget"] is not None]
    assert len(budgeted) >= 1

    food_status = next(s for s in budgeted if s["group_name"] == "Food & Dining")
    assert food_status["monthly_spent"] == pytest.approx(50.0)
    assert food_status["monthly_budget"] == pytest.approx(500.0)
    assert food_status["monthly_health"] == "on_track"
