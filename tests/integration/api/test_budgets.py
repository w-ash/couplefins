from datetime import UTC, datetime

from httpx import AsyncClient
import pytest

from tests.integration.conftest import CookieAuth, setup_and_login, upload_csv


async def _get_group_id(client: AsyncClient, name: str, auth: CookieAuth) -> str:
    """Look up a seeded category group by name."""
    resp = await client.get("/api/v1/category-groups", auth=auth)
    return next(g["id"] for g in resp.json() if g["name"] == name)


async def test_budget_overview_empty(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 1
    assert all(s["monthly_budget"] is None for s in data["group_statuses"])
    assert all(s["monthly_spent"] == pytest.approx(0.0) for s in data["group_statuses"])
    assert data["budgets"] == []


async def test_create_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Food & Dining", cookies)

    response = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["group_id"] == group_id
    assert data["monthly_amount"] == pytest.approx(500.0)
    assert data["year"] == 2026
    assert data["month"] == 1
    assert "id" in data


async def test_update_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Housing", cookies)

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )
    budget_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/budgets/{budget_id}",
        json={"monthly_amount": 600.0},
        auth=cookies,
    )
    assert response.status_code == 200
    assert response.json()["monthly_amount"] == pytest.approx(600.0)


async def test_delete_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Shopping", cookies)

    create_resp = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 300.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )
    budget_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/budgets/{budget_id}", auth=cookies)
    assert response.status_code == 204


async def test_delete_nonexistent_budget_returns_404(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/budgets/{fake_id}", auth=cookies)
    assert response.status_code == 404


async def test_list_budgets(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Health & Wellness", cookies)

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 200.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )

    response = await client.get("/api/v1/budgets", auth=cookies)
    assert response.status_code == 200
    budgets = response.json()
    assert len(budgets) >= 1
    assert any(b["group_id"] == group_id for b in budgets)


async def test_overview_with_budget_and_spending(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    group_id = await _get_group_id(client, "Food & Dining", cookies)

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Restaurants & Bars,Chase,,,-50.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()

    budgeted = [s for s in data["group_statuses"] if s["monthly_budget"] is not None]
    assert len(budgeted) >= 1

    food_status = next(s for s in budgeted if s["group_name"] == "Food & Dining")
    assert food_status["monthly_spent"] == pytest.approx(50.0)
    assert food_status["monthly_budget"] == pytest.approx(500.0)
    assert food_status["monthly_health"] == "on_track"


async def test_ytd_categories_include_earlier_month_only_category(
    client: AsyncClient,
) -> None:
    """A category spent in an earlier month but not the viewed month must
    still appear in ytd_categories, even though it's absent from the
    (current-month) categories list."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-10,Coffee Shop,Coffee Shops,Chase,,,-20.00,shared\n"
        "2026-02-15,Restaurant,Restaurants & Bars,Chase,,,-50.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=2", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()

    food_status = next(
        s for s in data["group_statuses"] if s["group_name"] == "Food & Dining"
    )
    monthly_cats = {c["category"] for c in food_status["categories"]}
    ytd_cats = {c["category"] for c in food_status["ytd_categories"]}
    assert monthly_cats == {"Restaurants & Bars"}
    assert ytd_cats == {"Restaurants & Bars", "Coffee Shops"}


async def test_overview_surfaces_uncategorized_row(client: AsyncClient) -> None:
    """A brand-new category (auto-created with group_id=None on upload) gets
    its own Uncategorized status instead of vanishing from every total."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]

    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Mystery Shop,Totally New Category,Chase,,,-40.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()

    uncategorized = next(
        s for s in data["group_statuses"] if s["group_name"] == "Uncategorized"
    )
    assert uncategorized["group_id"] is None
    assert uncategorized["monthly_budget"] is None
    assert uncategorized["monthly_spent"] == pytest.approx(40.0)
    assert data["spending_drift"] is None


async def test_create_personal_budget(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Food & Dining", cookies)

    response = await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 300.0,
            "year": 2026,
            "month": 1,
            "is_personal": True,
        },
        auth=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["person_id"] is not None
    assert data["monthly_amount"] == pytest.approx(300.0)


async def test_personal_budget_overview(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    group_id = await _get_group_id(client, "Food & Dining", cookies)

    # Create personal budget for Alice
    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 400.0,
            "year": 2026,
            "month": 1,
            "is_personal": True,
        },
        auth=cookies,
    )

    # Upload shared transaction (Alice pays $100 shared 50/50)
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Restaurant,Restaurants & Bars,Chase,,,-100.00,shared\n"
    )
    await upload_csv(client, alice_id, csv, auth=cookies)

    response = await client.get(
        f"/api/v1/budgets/overview?year=2026&month=1&scope=personal&person_id={alice_id}",
        auth=cookies,
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


async def test_default_scope_reports_household_source_split(
    client: AsyncClient,
) -> None:
    """Household scope: spending is all household rows (no include_personal
    categories are seeded), so the split is (monthly_spent, 0) per group."""
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()
    for status in data["group_statuses"]:
        assert status["household_spending"] == pytest.approx(status["monthly_spent"])
        assert status["personal_spending"] == pytest.approx(0.0)


async def test_copy_budgets_end_to_end(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Food & Dining", cookies)

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 500.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )

    response = await client.post(
        "/api/v1/budgets/copy",
        json={
            "source_year": 2026,
            "source_month": 1,
            "target_year": 2026,
            "target_month": 2,
        },
        auth=cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["copied_count"] == 1
    assert data["skipped_count"] == 0

    overview = await client.get(
        "/api/v1/budgets/overview?year=2026&month=2", auth=cookies
    )
    feb_budgets = overview.json()["budgets"]
    assert len(feb_budgets) == 1
    assert feb_budgets[0]["group_id"] == group_id
    assert feb_budgets[0]["monthly_amount"] == pytest.approx(500.0)


async def test_copy_skips_existing_targets(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Travel & Lifestyle", cookies)

    # Create budget in Jan and Feb for same group
    for month in (1, 2):
        await client.post(
            "/api/v1/budgets",
            json={
                "group_id": group_id,
                "monthly_amount": 300.0,
                "year": 2026,
                "month": month,
            },
            auth=cookies,
        )

    response = await client.post(
        "/api/v1/budgets/copy",
        json={
            "source_year": 2026,
            "source_month": 1,
            "target_year": 2026,
            "target_month": 2,
        },
        auth=cookies,
    )
    assert response.status_code == 201
    assert response.json()["copied_count"] == 0
    assert response.json()["skipped_count"] == 1


async def test_copy_to_finalized_month_returns_409(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 2},
        auth=cookies,
    )

    response = await client.post(
        "/api/v1/budgets/copy",
        json={
            "source_year": 2026,
            "source_month": 1,
            "target_year": 2026,
            "target_month": 2,
        },
        auth=cookies,
    )
    assert response.status_code == 409


async def test_overview_includes_copyable_source(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Travel & Lifestyle", cookies)

    await client.post(
        "/api/v1/budgets",
        json={
            "group_id": group_id,
            "monthly_amount": 200.0,
            "year": 2026,
            "month": 1,
        },
        auth=cookies,
    )

    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=2", auth=cookies
    )
    assert response.status_code == 200
    data = response.json()
    assert data["copyable_source"] == {"year": 2026, "month": 1}
    assert data["next_month_has_budgets"] is False
    assert len(data["source_budgets"]) == 1


async def test_budget_on_transfer_group_rejected(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    group_id = await _get_group_id(client, "Transfers", cookies)

    response = await client.post(
        "/api/v1/budgets",
        json={"group_id": group_id, "monthly_amount": 100.0, "year": 2026, "month": 1},
        auth=cookies,
    )
    assert response.status_code == 422
    assert "Only spending groups" in response.text


async def test_overview_has_no_transfer_row(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    response = await client.get(
        "/api/v1/budgets/overview?year=2026&month=1", auth=cookies
    )
    names = {s["group_name"] for s in response.json()["group_statuses"]}
    assert "Transfer" not in names
    assert "Food & Dining" in names


async def test_overview_defaults_to_the_latest_month_with_spending(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-10,Coffee Shop,Coffee Shops,Chase,,,-20.00,shared\n"
        "2026-02-15,Restaurant,Restaurants & Bars,Chase,,,-50.00,shared\n"
    )
    await upload_csv(client, persons[0]["id"], csv, auth=cookies)

    response = await client.get("/api/v1/budgets/overview", auth=cookies)
    assert response.status_code == 200

    data = response.json()
    assert (data["year"], data["month"]) == (2026, 2)


async def test_overview_with_no_data_defaults_to_today(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    response = await client.get("/api/v1/budgets/overview", auth=cookies)
    assert response.status_code == 200

    now = datetime.now(UTC)
    data = response.json()
    assert (data["year"], data["month"]) == (now.year, now.month)
