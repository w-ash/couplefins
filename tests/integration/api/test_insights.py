from httpx import AsyncClient
import pytest

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

    assert "comparison_cards" in data
    assert "persons" in data
    assert "month" in data
    assert len(data["persons"]) == 2


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
    assert data["category_comparisons"] == []
    assert data["month_flow"] == {
        "cells": [],
        "top_merchants": [],
        "largest_transactions": [],
    }


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


async def test_spending_trends_flow_household_sources_are_payers(
    client: AsyncClient,
) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)
    bob = await login_as_bob(client)
    await upload_csv(client, persons[1]["id"], BOB_CSV, auth=bob)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "month": 1},
        auth=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()

    cells = data["month_flow"]["cells"]
    assert {c["source_kind"] for c in cells} == {"payer"}
    assert {c["source_person_id"] for c in cells} == {
        persons[0]["id"],
        persons[1]["id"],
    }
    assert {c["category"] for c in cells} == {
        "Dining Out",
        "Groceries & Home Supplies",
        "Gas",
    }
    assert sum(c["amount"] for c in cells) == pytest.approx(
        data["monthly_totals"][0]["total_amount"]
    )
    # Year to date through January is January alone.
    assert sum(c["amount"] for c in data["ytd_flow"]["cells"]) == pytest.approx(150)
    assert [m["merchant"] for m in data["month_flow"]["top_merchants"]] == [
        "Grocery Store",
        "Gas Station",
        "Sushi Place",
    ]
    assert data["month_flow"]["largest_transactions"][0]["merchant"] == "Grocery Store"


async def test_spending_trends_category_comparisons(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=cookies)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "month": 2},
        auth=cookies,
    )
    assert resp.status_code == 200
    comparisons = {c["category"]: c for c in resp.json()["category_comparisons"]}
    assert comparisons["Dining Out"]["current_month_amount"] == pytest.approx(30)
    assert comparisons["Dining Out"]["trailing_average"] == pytest.approx(40)
    assert comparisons["Groceries & Home Supplies"]["current_month_amount"] == 0


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
    bob_data = bob_resp.json()
    assert bob_data["monthly_totals"] == [
        {"year": 2026, "month": 1, "total_amount": 60.0}
    ]
    # Each person's flow names their claim on the row.
    assert {
        (c["source_kind"], c["amount"]) for c in alice_data["month_flow"]["cells"]
    } == {
        ("household_share", 70.0),
        ("personal", 40.0),
    }
    assert {
        (c["source_kind"], c["amount"]) for c in bob_data["month_flow"]["cells"]
    } == {
        ("household_share", 30.0),
        ("spotted_for_me", 30.0),
    }


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


PAYCHECK_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-05,Employer,Paychecks,Chase,PAYROLL,,5000.00,
2026-01-11,Book Store,Dining Out,Chase,BOOK STORE,,-40.00,
"""


async def test_paychecks_are_not_personal_spending(client: AsyncClient) -> None:
    persons, alice = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], PAYCHECK_CSV, auth=alice)

    resp = await client.get(
        "/api/v1/insights/spending-trends",
        params={"year": 2026, "month": 1, "scope": "personal"},
        auth=alice,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_totals"] == [{"year": 2026, "month": 1, "total_amount": 40.0}]
    assert [c["category"] for c in data["month_flow"]["cells"]] == ["Dining Out"]
