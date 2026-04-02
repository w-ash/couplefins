from httpx import AsyncClient
import pytest

from tests.integration.conftest import setup_and_login, upload_csv


async def test_budget_overview_empty(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert data["group_statuses"] == []
    assert data["budgets"] == []


async def test_create_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    response = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["group_id"] == group_id
    assert data["monthly_amount"] == pytest.approx(500.0)
    assert data["effective_from"] == "2026-01-01"
    assert "id" in data


async def test_update_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Home Expenses"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
        cookies=cookies,
    )
    budget_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/budgets/{budget_id}",
        json={"monthly_amount": 600.0},
        cookies=cookies,
    )
    assert response.status_code == 200
    assert response.json()["monthly_amount"] == pytest.approx(600.0)


async def test_delete_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Shopping"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 300.0,
            "effective_from": "2026-01-01",
        },
        cookies=cookies,
    )
    budget_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/budgets/{budget_id}", cookies=cookies)
    assert response.status_code == 204


async def test_delete_nonexistent_budget_returns_404(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/budgets/{fake_id}", cookies=cookies)
    assert response.status_code == 404


async def test_list_budgets(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Health"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 200.0,
            "effective_from": "2026-01-01",
        },
        cookies=cookies,
    )

    response = await client.get("/api/v1/budgets", cookies=cookies)
    assert response.status_code == 200
    budgets = response.json()
    assert len(budgets) >= 1
    assert any(b["group_id"] == group_id for b in budgets)


async def test_overview_with_budget_and_spending(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    await client.put(
        "/api/v1/category-mappings",
        json={"mappings": [{"category": "Dining Out", "group_id": group_id}]},
        cookies=cookies,
    )

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "effective_from": "2026-01-01",
        },
        cookies=cookies,
    )

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Dining Out,Chase,,,-50.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()

    budgeted = [s for s in data["group_statuses"] if s["monthly_budget"] is not None]
    assert len(budgeted) >= 1

    food_status = next(s for s in budgeted if s["group_name"] == "Food & Dining")
    assert food_status["monthly_spent"] == pytest.approx(50.0)
    assert food_status["monthly_budget"] == pytest.approx(500.0)
    assert food_status["monthly_health"] == "on_track"


async def test_create_personal_budget(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    response = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 300.0,
            "effective_from": "2026-01-01",
            "person_id": alice_id,
        },
        cookies=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["person_id"] == alice_id
    assert data["monthly_amount"] == pytest.approx(300.0)


async def test_personal_budget_overview(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    group_resp = await client.post(
        "/api/v1/category-groups", json={"name": "Food & Dining"}, cookies=cookies
    )
    group_id = group_resp.json()["id"]

    await client.put(
        "/api/v1/category-mappings",
        json={"mappings": [{"category": "Dining Out", "group_id": group_id}]},
        cookies=cookies,
    )

    # Create personal budget for Alice
    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 400.0,
            "effective_from": "2026-01-01",
            "person_id": alice_id,
        },
        cookies=cookies,
    )

    # Upload shared transaction (Alice pays $100 shared 50/50)
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Dining Out,Chase,,,-100.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, cookies=cookies)

    response = await client.get(
        f"/api/v1/budgets/overview?year=2026&month=1&scope=personal&person_id={alice_id}",
        cookies=cookies,
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["group_statuses"]) >= 1
    food = next(s for s in data["group_statuses"] if s["group_name"] == "Food & Dining")
    # Alice's share of $100 @ 50% = $50
    assert food["household_spending"] == pytest.approx(50.0)
    assert food["personal_spending"] == pytest.approx(0.0)
    assert food["monthly_spent"] == pytest.approx(50.0)
    assert food["monthly_budget"] == pytest.approx(400.0)


async def test_default_scope_backward_compatible(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", cookies=cookies
    )
    assert response.status_code == 200
    data = response.json()
    # Household scope: shared/personal_spending should be null
    for status in data["group_statuses"]:
        assert status["household_spending"] is None
        assert status["personal_spending"] is None
