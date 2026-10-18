"""v1.15.5 routes: the home's loans and what comes due (US-HOUSE-12, -13)."""

from datetime import UTC, date, datetime
from uuid import UUID

from httpx import AsyncClient
import pytest

from src.domain.date_math import add_months
from tests.integration.api._joint import (
    HEADER,
    JOINT_LABEL,
    couple_with_joint_exports,
    january,
    mark_joint,
)
from tests.integration.conftest import (
    CookieAuth,
    setup_and_login,
    setup_couple,
    upload_csv,
)

ASSET_BODY = {
    "name": "Home",
    "repair_threshold": 500,
    "qualifying_kinds": ["closing", "loan-interest", "loan-principal"],
}
MORTGAGE = {
    "name": "Mortgage",
    "lender": "Example Bank",
    "kind": "amortizing",
    "principal": 300000,
    "annual_rate": 6.0,
    "payment": 1798.65,
    "term_months": 360,
    "first_due_on": "2026-02-01",
    "statement_balance": 300000,
    "statement_balance_as_of": "2026-01-01",
}
BRIDGE = {
    **MORTGAGE,
    "name": "Bridge loan",
    "lender": "Example Credit Union",
    "kind": "interest_only",
    "annual_rate": 8.5,
    "payment": 2125,
    "term_months": 12,
    "first_due_on": "2026-02-01",
    "statement_balance_as_of": "2025-10-01",
}
TAX = {
    "kind": "property_tax",
    "description": "Property tax, first installment",
    "amount": 2400,
    "is_estimate": True,
    "due_on": "2026-01-20",
    "late_after": "2026-02-10",
    "pays_from": "bills",
}
# Alice pays the mortgage from her own card and keeps it in full.
PAYMENT_CSV = (
    HEADER + '2026-02-01,Example Bank,Mortgage,Chase,EXAMPLE BANK,,"-1798.65",'
    '"s100, loan:mortgage"\n'
)


async def _home(client: AsyncClient) -> CookieAuth:
    _, auth = await setup_and_login(client)
    response = await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    assert response.status_code == 200, response.text
    return auth


async def _post(client: AsyncClient, path: str, body: dict, auth: CookieAuth) -> dict:
    response = await client.post(f"/api/v1/house{path}", json=body, auth=auth)
    assert response.status_code == 201, response.text
    return response.json()


async def _house(client: AsyncClient, auth: CookieAuth) -> dict:
    response = await client.get("/api/v1/house", auth=auth)
    assert response.status_code == 200, response.text
    return response.json()


def _this_months_first() -> str:
    """The next due date of a loan due on the 1st with no payment
    obligation: its dates are open from the first of this month."""
    return datetime.now(UTC).date().replace(day=1).isoformat()


async def test_the_loan_and_obligation_routes_require_login(
    client: AsyncClient,
) -> None:
    await setup_couple(client)
    some_id = UUID(int=1)

    for method, path in [
        ("GET", "/loans"),
        ("POST", "/loans"),
        ("POST", f"/loans/{some_id}/replace"),
        ("POST", f"/loans/{some_id}/close"),
        ("PUT", f"/loans/{some_id}/statement"),
        ("DELETE", f"/loans/{some_id}"),
        ("POST", f"/loans/{some_id}/payment-obligations"),
        ("GET", "/obligations"),
        ("POST", "/obligations"),
        ("PUT", f"/obligations/{some_id}"),
        ("DELETE", f"/obligations/{some_id}"),
        ("PUT", f"/obligations/{some_id}/payment"),
        ("GET", f"/obligations/{some_id}/candidates"),
    ]:
        response = await client.request(method, f"/api/v1/house{path}", json={})
        assert response.status_code == 401, (method, path)


async def test_loans_and_obligations_need_the_home_first(client: AsyncClient) -> None:
    _, auth = await setup_and_login(client)

    loan = await client.post("/api/v1/house/loans", json=MORTGAGE, auth=auth)
    obligation = await client.post("/api/v1/house/obligations", json=TAX, auth=auth)

    assert (loan.status_code, obligation.status_code) == (422, 422)
    assert "Settings" in loan.json()["error"]["message"]
    assert (await client.get("/api/v1/house/loans", auth=auth)).json() == []
    assert (await client.get("/api/v1/house/obligations", auth=auth)).json() == []


async def test_a_recorded_loan_is_listed_and_real_on_the_house_page(
    client: AsyncClient,
) -> None:
    """US-HOUSE-8, -12: with the home set up, every section is real."""
    auth = await _home(client)

    loan = await _post(client, "/loans", MORTGAGE, auth)

    assert {k: v for k, v in loan.items() if k not in {"id", "created_at"}} == {
        **MORTGAGE,
        "principal": 300000.0,
        "statement_balance": 300000.0,
        "slug": "mortgage",
        "tag": "loan:mortgage",
        "replaced_by_loan_id": None,
        "closed_on": None,
        "notes": "",
    }
    assert (await client.get("/api/v1/house/loans", auth=auth)).json() == [loan]
    house = await _house(client, auth)
    assert house["example_sections"] == []
    assert house["past_loans"] == house["upcoming"] == house["recent_paid"] == []
    [shown] = house["loans"]
    assert {k: v for k, v in shown.items() if k != "owner_parts"} == {
        "id": loan["id"],
        "name": "Mortgage",
        "lender": "Example Bank",
        "kind": "amortizing",
        "principal": 300000.0,
        "balance": 300000.0,
        "rate_percent": 6.0,
        "payment": 1798.65,
        "statement_balance": 300000.0,
        "statement_balance_as_of": "2026-01-01",
        "next_due": _this_months_first(),
    }
    assert [p["amount"] for p in shown["owner_parts"]] == [899.33, 899.32]


@pytest.mark.parametrize(
    "change",
    [
        {"name": "MORTGAGE!"},  # the same slug as the first
        {"name": "%%"},  # no slug
        {"kind": "balloon"},  # the schema's type
        {"principal": 0},  # the loan
        {"lender": " "},  # the terms
    ],
)
async def test_an_invalid_loan_is_rejected(
    client: AsyncClient, change: dict[str, object]
) -> None:
    auth = await _home(client)
    await _post(client, "/loans", MORTGAGE, auth)

    response = await client.post(
        "/api/v1/house/loans", json={**MORTGAGE, **change}, auth=auth
    )

    assert response.status_code == 422, response.text


async def test_a_refinance_replaces_the_loan_and_keeps_its_history(
    client: AsyncClient,
) -> None:
    auth = await _home(client)
    bridge = await _post(client, "/loans", BRIDGE, auth)

    # The refinance pays the bridge loan off before its first due date.
    replaced = await _post(
        client,
        f"/loans/{bridge['id']}/replace",
        {**MORTGAGE, "closed_on": "2026-01-31"},
        auth,
    )

    old, new = replaced["replaced"], replaced["replacement"]
    assert (old["id"], old["closed_on"]) == (bridge["id"], "2026-01-31")
    assert old["replaced_by_loan_id"] == new["id"]
    assert (new["slug"], new["closed_on"]) == ("mortgage", None)
    house = await _house(client, auth)
    assert [loan["id"] for loan in house["loans"]] == [new["id"]]
    [past] = house["past_loans"]
    assert (past["id"], past["closed_on"], past["replaced_by_loan_id"]) == (
        bridge["id"],
        "2026-01-31",
        new["id"],
    )
    assert past["balance"] == pytest.approx(300000)
    again = await client.post(
        f"/api/v1/house/loans/{bridge['id']}/replace",
        json={**MORTGAGE, "name": "Second mortgage", "closed_on": "2026-02-28"},
        auth=auth,
    )
    assert again.status_code == 422
    kept = await client.delete(f"/api/v1/house/loans/{new['id']}", auth=auth)
    assert (kept.status_code, "replaced" in kept.json()["error"]["message"]) == (
        422,
        True,
    )

    closed = await client.post(
        f"/api/v1/house/loans/{new['id']}/close",
        json={"closed_on": "2026-06-30"},
        auth=auth,
    )

    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_on"] == "2026-06-30"
    house = await _house(client, auth)
    assert house["loans"] == []
    assert {p["id"] for p in house["past_loans"]} == {bridge["id"], new["id"]}
    no_more = await client.post(
        f"/api/v1/house/loans/{new['id']}/payment-obligations",
        json={"months": 1},
        auth=auth,
    )
    assert no_more.status_code == 422
    unknown = await client.post(
        f"/api/v1/house/loans/{UUID(int=5)}/close",
        json={"closed_on": "2026-06-30"},
        auth=auth,
    )
    assert unknown.status_code == 404


async def test_a_linked_payment_lowers_the_balance_until_a_statement_re_anchors(
    client: AsyncClient,
) -> None:
    """A payment from an owner's own account counts; its payer keeps it in
    full, so their part of the payment is all of it."""
    persons, auth = await setup_and_login(client)
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    await upload_csv(client, persons[0]["id"], PAYMENT_CSV, auth=auth)
    loan = await _post(client, "/loans", MORTGAGE, auth)

    [shown] = (await _house(client, auth))["loans"]
    assert shown["balance"] == pytest.approx(299701.35)
    assert [p["amount"] for p in shown["owner_parts"]] == [1798.65, 0.0]

    anchored = await client.put(
        f"/api/v1/house/loans/{loan['id']}/statement",
        json={"balance": 299500, "as_of": "2026-02-15"},
        auth=auth,
    )

    assert anchored.status_code == 200, anchored.text
    assert (
        anchored.json()["statement_balance"],
        anchored.json()["statement_balance_as_of"],
    ) == (299500.0, "2026-02-15")
    # The payment is in the new statement, so it no longer counts.
    [shown] = (await _house(client, auth))["loans"]
    assert shown["balance"] == pytest.approx(299500)
    negative = await client.put(
        f"/api/v1/house/loans/{loan['id']}/statement",
        json={"balance": -1, "as_of": "2026-02-15"},
        auth=auth,
    )
    assert negative.status_code == 422


async def test_a_loan_is_deleted_only_before_it_has_history(
    client: AsyncClient,
) -> None:
    persons, auth = await setup_and_login(client)
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    await upload_csv(client, persons[0]["id"], PAYMENT_CSV, auth=auth)
    tagged = await _post(client, "/loans", MORTGAGE, auth)
    with_obligation = await _post(
        client, "/loans", {**MORTGAGE, "name": "Second mortgage"}, auth
    )
    await _post(
        client,
        f"/loans/{with_obligation['id']}/payment-obligations",
        {"months": 1},
        auth,
    )
    fresh = await _post(client, "/loans", {**MORTGAGE, "name": "Typo loan"}, auth)

    async def delete(loan_id: object) -> tuple[int, dict]:
        response = await client.delete(f"/api/v1/house/loans/{loan_id}", auth=auth)
        return response.status_code, response.json()

    assert await delete(fresh["id"]) == (200, {"deleted": True})
    status, body = await delete(tagged["id"])
    assert (status, "loan:mortgage" in body["error"]["message"]) == (422, True)
    assert (await delete(with_obligation["id"]))[0] == 422
    assert (await delete(UUID(int=9)))[0] == 404
    listed = (await client.get("/api/v1/house/loans", auth=auth)).json()
    assert {loan["id"] for loan in listed} == {tagged["id"], with_obligation["id"]}


async def test_a_loans_next_payments_are_generated_as_obligations(
    client: AsyncClient,
) -> None:
    auth = await _home(client)
    loan = await _post(client, "/loans", MORTGAGE, auth)
    path = f"/loans/{loan['id']}/payment-obligations"

    first = await _post(client, path, {"months": 2}, auth)
    then = await _post(client, path, {"months": 1}, auth)

    start = date.fromisoformat(_this_months_first())
    assert [o["due_on"] for o in (*first, *then)] == [
        add_months(start, n).isoformat() for n in range(3)
    ]
    assert {
        (o["kind"], o["loan_id"], o["amount"], o["pays_from"], o["description"])
        for o in first
    } == {("loan_payment", loan["id"], 1798.65, None, "Mortgage payment")}
    house = await _house(client, auth)
    assert [o["id"] for o in house["upcoming"]] == [o["id"] for o in (*first, *then)]
    assert house["loans"][0]["next_due"] == first[0]["due_on"]
    for months in (0, 25):
        response = await client.post(
            f"/api/v1/house{path}", json={"months": months}, auth=auth
        )
        assert response.status_code == 422, months


async def test_an_obligation_is_entered_edited_and_deleted(
    client: AsyncClient,
) -> None:
    auth = await _home(client)

    tax = await _post(client, "/obligations", TAX, auth)

    assert {k: v for k, v in tax.items() if k != "id"} == {
        **TAX,
        "amount": 2400.0,
        "loan_id": None,
        "paid_by_transaction_id": None,
        "notes": "",
    }
    billed = await client.put(
        f"/api/v1/house/obligations/{tax['id']}",
        json={**TAX, "amount": 2512.4, "is_estimate": False, "pays_from": "  "},
        auth=auth,
    )
    assert billed.status_code == 200, billed.text
    assert (
        billed.json()["amount"],
        billed.json()["is_estimate"],
        billed.json()["pays_from"],
    ) == (2512.4, False, None)
    listed = (await client.get("/api/v1/house/obligations", auth=auth)).json()
    assert listed == [billed.json()]
    [upcoming] = (await _house(client, auth))["upcoming"]
    assert (upcoming["name"], upcoming["status"], upcoming["late_after"]) == (
        TAX["description"],
        "late",
        "2026-02-10",
    )

    deleted = await client.delete(f"/api/v1/house/obligations/{tax['id']}", auth=auth)

    assert deleted.json() == {"deleted": True}
    assert (await client.get("/api/v1/house/obligations", auth=auth)).json() == []
    for method, path, body in [
        ("PUT", f"/obligations/{tax['id']}", TAX),
        ("DELETE", f"/obligations/{tax['id']}", None),
        (
            "POST",
            "/obligations",
            {**TAX, "kind": "loan_payment", "loan_id": str(UUID(int=3))},
        ),
    ]:
        response = await client.request(
            method, f"/api/v1/house{path}", json=body, auth=auth
        )
        assert response.status_code == 404, (method, path)


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "loan_payment"},  # no loan
        {"amount": 0},
        {"late_after": "2026-01-01"},  # before the due date
        {"description": ""},
        {"kind": "rent"},  # the schema's type
    ],
)
async def test_an_invalid_obligation_is_rejected(
    client: AsyncClient, change: dict[str, object]
) -> None:
    auth = await _home(client)

    response = await client.post(
        "/api/v1/house/obligations", json={**TAX, **change}, auth=auth
    )

    assert response.status_code == 422, response.text


async def test_linking_its_payment_makes_an_obligation_paid(
    client: AsyncClient,
) -> None:
    """US-HOUSE-13: candidates near the due date and amount; a linked
    obligation leaves Upcoming; unlinking brings it back."""
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)
    auth = couple.alice
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    rows = (await january(client, auth))["transactions"]
    hardware = next(r for r in rows if r["merchant"] == "Hardware Store")
    bill = await _post(
        client, "/obligations", {**TAX, "amount": 120, "due_on": "2026-01-12"}, auth
    )

    candidates = await client.get(
        f"/api/v1/house/obligations/{bill['id']}/candidates", auth=auth
    )

    assert candidates.status_code == 200
    first = candidates.json()[0]
    assert (first["id"], first["score"], first["amount"]) == (
        hardware["id"],
        5,
        -120.0,
    )
    assert first["account_name"] == JOINT_LABEL
    paid = await client.put(
        f"/api/v1/house/obligations/{bill['id']}/payment",
        json={"transaction_id": hardware["id"]},
        auth=auth,
    )
    assert paid.json()["paid_by_transaction_id"] == hardware["id"]
    house = await _house(client, auth)
    assert house["upcoming"] == []
    [recent] = house["recent_paid"]
    assert (recent["id"], recent["status"], recent["paid_by_transaction_id"]) == (
        bill["id"],
        "paid",
        hardware["id"],
    )

    unpaid = await client.put(
        f"/api/v1/house/obligations/{bill['id']}/payment",
        json={"transaction_id": None},
        auth=auth,
    )

    assert unpaid.json()["paid_by_transaction_id"] is None
    assert [o["id"] for o in (await _house(client, auth))["upcoming"]] == [bill["id"]]
    missing = await client.put(
        f"/api/v1/house/obligations/{bill['id']}/payment",
        json={"transaction_id": str(UUID(int=4))},
        auth=auth,
    )
    assert missing.status_code == 404
    unknown = await client.get(
        f"/api/v1/house/obligations/{UUID(int=4)}/candidates", auth=auth
    )
    assert unknown.status_code == 404


async def test_a_row_pays_one_obligation_at_most(client: AsyncClient) -> None:
    """US-HOUSE-13: once a row pays a bill, another bill is not offered it,
    and linking it there is refused."""
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)
    auth = couple.alice
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    rows = (await january(client, auth))["transactions"]
    hardware = next(r for r in rows if r["merchant"] == "Hardware Store")
    bill, other = [
        await _post(client, "/obligations", {**TAX, "amount": 120, "due_on": day}, auth)
        for day in ("2026-01-12", "2026-01-13")
    ]
    await client.put(
        f"/api/v1/house/obligations/{bill['id']}/payment",
        json={"transaction_id": hardware["id"]},
        auth=auth,
    )

    offered = await client.get(
        f"/api/v1/house/obligations/{other['id']}/candidates", auth=auth
    )
    taken = await client.put(
        f"/api/v1/house/obligations/{other['id']}/payment",
        json={"transaction_id": hardware["id"]},
        auth=auth,
    )

    assert hardware["id"] not in {c["id"] for c in offered.json()}
    assert taken.status_code == 422
    assert "another obligation" in taken.json()["error"]["message"]


async def test_loans_and_paid_obligations_move_no_settlement_budget_or_dashboard(
    client: AsyncClient,
) -> None:
    """THE PIN (US-HOUSE-12, -13): Settle Up, the budgets, and the dashboard
    read the same before and after a loan is recorded, a joint row is tagged
    as its interest, and an obligation is marked paid by that row."""
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)
    auth = couple.bob
    month = {"year": 2026, "month": 1}
    reads = [
        ("/api/v1/settle-up", month),
        ("/api/v1/budgets/overview", month),
        ("/api/v1/budgets/overview", {**month, "scope": "personal"}),
        ("/api/v1/dashboard", month),
    ]

    async def snapshot() -> list[dict]:
        return [
            (await client.get(path, params=params, auth=auth)).json()
            for path, params in reads
        ]

    before = await snapshot()
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    loan = await _post(
        client, "/loans", {**MORTGAGE, "statement_balance_as_of": "2025-12-01"}, auth
    )
    rows = (await january(client, auth))["transactions"]
    hardware = next(r for r in rows if r["merchant"] == "Hardware Store")
    tagged = await client.post(
        "/api/v1/transactions/bulk-tags",
        json={
            "transaction_ids": [hardware["id"]],
            "action": "add",
            "tags": [loan["tag"], "share:loan-interest"],
        },
        auth=auth,
    )
    assert tagged.status_code == 200, tagged.text
    payment = await _post(
        client,
        "/obligations",
        {
            **TAX,
            "kind": "loan_payment",
            "description": "Mortgage payment",
            "loan_id": loan["id"],
            "due_on": "2026-01-12",
            "late_after": None,
        },
        auth,
    )
    paid = await client.put(
        f"/api/v1/house/obligations/{payment['id']}/payment",
        json={"transaction_id": hardware["id"]},
        auth=auth,
    )
    assert paid.status_code == 200, paid.text

    assert await snapshot() == before
    house = await _house(client, auth)
    # The tagged row is the loan's payment and an interest credit.
    [shown] = house["loans"]
    assert shown["balance"] == pytest.approx(300000)  # all interest at 6%
    assert [t["amount"] for t in house["put_in"]["totals"]] == [60.0, 60.0]
    assert [o["id"] for o in house["recent_paid"]] == [payment["id"]]
