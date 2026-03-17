from httpx import AsyncClient

from tests.integration.conftest import setup_couple, upload_csv

ALICE_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-10,Sushi Place,Dining Out,Chase,SUSHI PLACE,,-40.00,"shared"
2026-01-20,Grocery Store,Groceries & Home Supplies,Chase,GROCERY STORE,,-60.00,"shared"
2026-02-05,Pizza Joint,Dining Out,Chase,PIZZA JOINT,,-30.00,"shared"
"""

BOB_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-01-15,Gas Station,Gas,Chase,GAS STATION,,-50.00,"shared"
2026-02-10,Coffee Shop,Coffee Shops & Treats,Chase,COFFEE SHOP,,-15.00,"shared"
"""


async def test_spending_trends_with_data(client: AsyncClient) -> None:
    persons = await setup_couple(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV)
    await upload_csv(client, persons[1]["id"], BOB_CSV)

    resp = await client.get("/api/v1/insights/spending-trends", params={"year": 2026})
    assert resp.status_code == 200

    data = resp.json()
    assert data["year"] == 2026
    assert len(data["monthly_totals"]) == 2  # Jan + Feb
    assert len(data["group_summaries"]) > 0
    assert all("group_name" in gs for gs in data["group_summaries"])
    assert all("ytd_total" in gs for gs in data["group_summaries"])


async def test_spending_trends_empty_year(client: AsyncClient) -> None:
    await setup_couple(client)

    resp = await client.get("/api/v1/insights/spending-trends", params={"year": 2025})
    assert resp.status_code == 200

    data = resp.json()
    assert data["year"] == 2025
    assert data["monthly_group_spending"] == []
    assert data["monthly_totals"] == []
    assert data["group_summaries"] == []


async def test_spending_trends_defaults_to_current_year(client: AsyncClient) -> None:
    await setup_couple(client)

    resp = await client.get("/api/v1/insights/spending-trends")
    assert resp.status_code == 200
    assert resp.json()["year"] > 0
