from httpx import AsyncClient

from tests.integration.conftest import login_as_bob, setup_and_login, upload_csv

ALICE_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-10,Sushi Place,Dining Out,Chase,SUSHI PLACE,,-40.00,"shared"
2026-01-20,Grocery Store,Groceries & Home Supplies,Chase,GROCERY STORE,,-60.00,"shared"
2026-02-05,Pizza Joint,Dining Out,Chase,PIZZA JOINT,,-30.00,"shared"
"""

ALICE_2025_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2025-01-15,Taco Truck,Dining Out,Chase,TACO TRUCK,,-25.00,"shared"
"""

BOB_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-15,Gas Station,Gas,Chase,GAS STATION,,-50.00,"shared"
2026-02-10,Coffee Shop,Coffee Shops & Treats,Chase,COFFEE SHOP,,-15.00,"shared"
"""


async def test_spending_trends_with_data(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)
    await upload_csv(client, persons[1]["id"], BOB_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends", params={"year": 2026}, auth=cookies
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["year"] == 2026
    assert len(data["monthly_totals"]) == 2  # Jan + Feb
    assert len(data["group_summaries"]) > 0
    assert all("group_name" in gs for gs in data["group_summaries"])
    assert all("ytd_total" in gs for gs in data["group_summaries"])

    # v0.7.1 fields present
    assert "comparison_cards" in data
    assert "budget_lines" in data
    assert "settlement_trend" in data
    assert "persons" in data
    assert "month" in data

    assert len(data["persons"]) == 2
    assert len(data["settlement_trend"]) == 2  # Jan + Feb have settlements


async def test_spending_trends_empty_year(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    resp = await client.get(
        "/api/v1/insights/spending-trends", params={"year": 2025}, auth=cookies
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["year"] == 2025
    assert data["monthly_group_spending"] == []
    assert data["monthly_totals"] == []
    assert data["group_summaries"] == []
    assert data["comparison_cards"] == []
    assert data["budget_lines"] == []
    assert data["settlement_trend"] == []


async def test_spending_trends_defaults_to_current_year(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    resp = await client.get("/api/v1/insights/spending-trends", auth=cookies)
    assert resp.status_code == 200
    assert resp.json()["year"] > 0


async def test_spending_trends_with_month_param(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "month": 2},
        auth=cookies,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["month"] == 2


async def test_spending_trends_includes_persons(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    resp = await client.get(
        "/api/v1/insights/spending-trends", params={"year": 2026}, auth=cookies
    )
    assert resp.status_code == 200

    persons = resp.json()["persons"]
    assert len(persons) == 2
    names = {p["name"] for p in persons}
    assert names == {"Alice", "Bob"}


async def test_spending_trends_with_comparison_year(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)
    await upload_csv(client, persons[0]["id"], ALICE_2025_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "comparison_year": 2025},
        auth=cookies,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["monthly_group_spending"]) > 0
    assert len(data["comparison_monthly_group_spending"]) > 0
    assert data["comparison_monthly_group_spending"][0]["year"] == 2025


async def test_spending_trends_comparison_year_no_data(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "comparison_year": 2020},
        auth=cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["comparison_monthly_group_spending"] == []


async def test_spending_trends_categories_present(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends", params={"year": 2026}, auth=cookies
    )
    assert resp.status_code == 200

    data = resp.json()
    mgs = data["monthly_group_spending"]
    assert len(mgs) > 0
    # Each item should have categories
    for item in mgs:
        assert "categories" in item
        assert isinstance(item["categories"], list)


# --- scope ---

# Alice's export: a 70/30 split she paid, her own personal row, and a
# spot for Bob (his personal spending, fronted by her).
ALICE_SCOPED_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-10,Sushi Place,Dining Out,Chase,SUSHI PLACE,,-100.00,"shared, s70"
2026-01-11,Book Store,Dining Out,Chase,BOOK STORE,,-40.00,
2026-01-12,Parking Meter,Dining Out,Chase,PARKING METER,,-30.00,"bob"
"""


async def test_spending_trends_personal_scope_is_the_users_share(
    client: AsyncClient,
) -> None:
    persons, alice = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_SCOPED_CSV, auth=alice)
    bob = await login_as_bob(client)
    params = {"year": 2026, "month": 1, "scope": "personal"}

    alice_resp = await client.get(
        "/api/v1/insights/spending-trends", params=params, auth=alice
    )
    bob_resp = await client.get(
        "/api/v1/insights/spending-trends", params=params, auth=bob
    )
    assert alice_resp.status_code == 200
    assert bob_resp.status_code == 200

    alice_data = alice_resp.json()
    # Her 70% of sushi + her own book; the spot for Bob is $0 for her.
    assert alice_data["monthly_totals"] == [
        {"year": 2026, "month": 1, "total_amount": 110.0}
    ]
    # Bob's 30% of sushi + the parking Alice spotted for him.
    assert bob_resp.json()["monthly_totals"] == [
        {"year": 2026, "month": 1, "total_amount": 60.0}
    ]


async def test_spending_trends_default_scope_is_household(
    client: AsyncClient,
) -> None:
    persons, alice = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_SCOPED_CSV, auth=alice)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "month": 1},
        auth=alice,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Only the shared sushi row at its full amount.
    assert data["monthly_totals"] == [{"year": 2026, "month": 1, "total_amount": 100.0}]


async def test_spending_trends_rejects_unknown_scope(client: AsyncClient) -> None:
    _, alice = await setup_and_login(client)
    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "scope": "all"},
        auth=alice,
    )
    assert resp.status_code == 422


CARD_PAYMENT_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-10,Sushi Place,Dining Out,Chase,SUSHI PLACE,,-100.00,"shared"
2026-01-15,Chase Card,Credit Card Payment,Checking,CHASE PAYMENT,,-4000.00,"shared"
2026-01-15,Chase Card,Credit Card Payment,Chase,PAYMENT THANK YOU,,4000.00,
2026-01-20,Amex,Credit Card Payment,Checking,AMEX PAYMENT,,-900.00,
"""


async def test_credit_card_payments_are_not_spending(client: AsyncClient) -> None:
    persons, alice = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], CARD_PAYMENT_CSV, auth=alice)

    for scope, expected in (("household", 100.0), ("personal", 50.0)):
        resp = await client.get(
            "/api/v1/insights/spending-trends",
            params={"year": 2026, "month": 1, "scope": scope},
            auth=alice,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert [g["group_name"] for g in data["group_summaries"]] == ["Food & Dining"]
        assert data["monthly_totals"] == [
            {"year": 2026, "month": 1, "total_amount": expected}
        ]
