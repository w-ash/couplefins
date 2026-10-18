from uuid import UUID

from httpx import AsyncClient
import pytest

from tests.integration.api._joint import (
    ALICE_CSV,
    HEADER,
    JOINT_LABEL,
    couple_with_joint_exports,
    mark_joint,
)
from tests.integration.conftest import (
    login_as_bob,
    setup_and_login,
    setup_couple,
    upload_csv,
)

_SECTIONS = (
    "put_in",
    "shares",
    "loans",
    "past_loans",
    "upcoming",
    "recent_paid",
    "set_aside",
    "recent_activity",
)


async def test_house_serves_the_example_with_every_section_filled(
    client: AsyncClient,
) -> None:
    _, auth = await setup_and_login(client)

    response = await client.get("/api/v1/house", auth=auth)

    assert response.status_code == 200
    data = response.json()
    assert sorted(data["example_sections"]) == sorted(_SECTIONS)
    assert [p["name"] for p in data["persons"]] == ["Alice", "Bob"]
    for section in _SECTIONS:
        assert data[section], section
    assert isinstance(data["put_in"]["total"], float)
    assert isinstance(data["shares"]["now"][0]["percent"], float)
    assert isinstance(data["loans"][0]["owner_parts"][0]["amount"], float)


async def test_house_requires_login(client: AsyncClient) -> None:
    await setup_couple(client)

    response = await client.get("/api/v1/house")

    assert response.status_code == 401


async def test_recent_activity_is_real_once_an_account_is_joint(
    client: AsyncClient,
) -> None:
    """US-HOUSE-7: the joint account's rows replace the example activity."""
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)

    response = await client.get("/api/v1/house", auth=couple.bob)

    data = response.json()
    assert sorted(data["example_sections"]) == sorted(
        set(_SECTIONS) - {"recent_activity", "set_aside"}
    )
    assert [p["id"] for p in data["persons"]] == [couple.alice_id, couple.bob_id]
    activity = data["recent_activity"]
    assert [(r["date"], r["account_name"]) for r in activity] == [
        ("2026-01-20", JOINT_LABEL),
        ("2026-01-14", JOINT_LABEL),
        ("2026-01-12", JOINT_LABEL),
    ]
    grocery, deposit, _ = activity
    assert (grocery["kind"], grocery["amount"]) == ("payment", -60.0)
    assert [s["amount"] for s in grocery["shares"]] == [30.0, 30.0]
    # Marking names the deposit's depositor from its text; a deposit is
    # its depositor's alone, though its category is a transfer.
    assert (deposit["kind"], deposit["person_id"]) == ("deposit", couple.alice_id)
    assert [s["amount"] for s in deposit["shares"]] == [1500.0, 0.0]
    # Example sections name the same couple as the real one.
    assert {a["person_id"] for a in data["put_in"]["totals"]} == {
        couple.alice_id,
        couple.bob_id,
    }


async def test_every_section_is_example_without_a_joint_account(
    client: AsyncClient,
) -> None:
    _, auth = await setup_and_login(client)

    data = (await client.get("/api/v1/house", auth=auth)).json()

    assert sorted(data["example_sections"]) == sorted(_SECTIONS)


# A joint account's month: both owners deposit (Bob's is a gift), the
# mortgage is paid from the bills pot, money moves from bills to renovation,
# and a hardware bill carries no pot.
POTS_CSV = (
    HEADER
    + "2026-01-14,Transfer From Alice,Transfer,Joint Checking,"
    + 'TRANSFER FROM ALICE,,"1500.00",pot:bills\n'
    + "2026-01-15,Transfer From Bob,Transfer,Joint Checking,"
    + 'TRANSFER FROM BOB,,"800.00","pot:renovation, source:gift"\n'
    + "2026-01-16,Lender,Home Improvement,Joint Checking,"
    + 'LENDER,,"-1200.00","pot:bills, line:mortgage"\n'
    + '2026-01-17,Move,Transfer,Joint Checking,MOVE OUT,,"-200.00",pot:bills\n'
    + '2026-01-17,Move,Transfer,Joint Checking,MOVE IN,,"200.00",pot:renovation\n'
    + "2026-01-18,Hardware Store,Home Improvement,Joint Checking,"
    + 'HARDWARE STORE,,"-60.00",\n'
)


async def test_set_aside_lists_the_pots_once_an_account_is_joint(
    client: AsyncClient,
) -> None:
    """v1.15.3: each pot's balance from the joint rows' `pot:` tags, and each
    owner's unspent deposits (deposits less their share of payments)."""
    persons, alice = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], POTS_CSV, auth=alice)
    await mark_joint(client, alice)

    data = (await client.get("/api/v1/house", auth=alice)).json()

    assert "set_aside" not in data["example_sections"]
    assert "put_in" in data["example_sections"]
    set_aside = data["set_aside"]
    assert [
        (b["name"], b["balance"], b["bank_balance"], b["is_unassigned"])
        for b in set_aside["buckets"]
    ] == [
        ("bills", 100.0, None, False),
        ("renovation", 1000.0, None, False),
        ("Unassigned", -60.0, None, True),
    ]
    assert set_aside["total"] == pytest.approx(1040.0)
    # Spending 1200 + 60 at 50/50; the transfer legs are no payment.
    assert [
        (
            o["person_id"],
            o["own_deposits"],
            o["gift_deposits"],
            o["share_of_payments"],
            o["unspent"],
        )
        for o in set_aside["owners"]
    ] == [
        (persons[0]["id"], 1500.0, 0.0, 630.0, 870.0),
        (persons[1]["id"], 0.0, 800.0, 630.0, 170.0),
    ]


# --- v1.15.4: the asset, hand-entered credits, and owner shares ---

ASSET_BODY = {
    "name": "Home",
    "repair_threshold": 500,
    "qualifying_kinds": ["closing", "loan-interest", "repair"],
    "bank_balance": 1234.56,
    "bank_balance_as_of": "2026-10-01",
}


def _credit(persons: list[dict], **overrides: object) -> dict:
    """Closing costs Alice and Bob paid 70/30 through escrow."""
    return {
        "date": "2026-01-20",
        "amount": 1000,
        "description": "Closing costs",
        "document_ref": "Closing statement p. 2",
        "share_kind": "closing",
        "owner_shares": {persons[0]["id"]: 70, persons[1]["id"]: 30},
        **overrides,
    }


async def test_the_asset_is_null_until_saved_then_updates_in_place(
    client: AsyncClient,
) -> None:
    """US-HOUSE-9: one asset per couple; saving again updates it."""
    _, auth = await setup_and_login(client)

    assert (await client.get("/api/v1/house/asset", auth=auth)).json() is None

    created = await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)
    assert created.status_code == 200, created.text
    asset = created.json()
    assert {k: asset[k] for k in ASSET_BODY} == {
        **ASSET_BODY,
        "repair_threshold": 500.0,
    }

    renamed = {
        **ASSET_BODY,
        "name": "The house",
        "bank_balance": None,
        "bank_balance_as_of": None,
    }
    updated = (await client.put("/api/v1/house/asset", json=renamed, auth=auth)).json()
    assert (updated["id"], updated["created_at"]) == (asset["id"], asset["created_at"])
    assert (updated["name"], updated["bank_balance"]) == ("The house", None)
    assert (await client.get("/api/v1/house/asset", auth=auth)).json() == updated


@pytest.mark.parametrize(
    "change",
    [
        {"qualifying_kinds": ["none"]},  # the schema's type
        {"name": " "},  # the command
        {"bank_balance": None},  # the command: a date with no balance
        {"repair_threshold": -1},  # the asset
    ],
)
async def test_an_invalid_asset_is_rejected(
    client: AsyncClient, change: dict[str, object]
) -> None:
    """Each layer's check reaches the client as a 422."""
    _, auth = await setup_and_login(client)

    response = await client.put(
        "/api/v1/house/asset", json={**ASSET_BODY, **change}, auth=auth
    )

    assert response.status_code == 422


async def test_the_new_house_routes_require_login(client: AsyncClient) -> None:
    await setup_couple(client)

    for method, path in [
        ("GET", "/api/v1/house/asset"),
        ("PUT", "/api/v1/house/asset"),
        ("GET", "/api/v1/house/manual-entries"),
        ("POST", "/api/v1/house/manual-entries"),
        ("DELETE", f"/api/v1/house/manual-entries/{UUID(int=1)}"),
    ]:
        response = await client.request(method, path, json=ASSET_BODY)
        assert response.status_code == 401, (method, path)


async def test_a_recorded_credit_moves_the_shares_and_deleting_it_undoes_it(
    client: AsyncClient,
) -> None:
    """US-HOUSE-10, -11: a hand-entered credit counts in Put in and Shares;
    deleting it takes it back out."""
    persons, auth = await setup_and_login(client)
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)

    posted = await client.post(
        "/api/v1/house/manual-entries", json=_credit(persons), auth=auth
    )

    assert posted.status_code == 201, posted.text
    entry = posted.json()
    assert {k: v for k, v in entry.items() if k != "id"} == {
        "account_name": "Escrow",
        "date": "2026-01-20",
        "amount": 1000.0,
        "description": "Closing costs",
        "document_ref": "Closing statement p. 2",
        "share_kind": "closing",
        "owner_shares": {persons[0]["id"]: 70, persons[1]["id"]: 30},
    }
    listed = (await client.get("/api/v1/house/manual-entries", auth=auth)).json()
    assert listed == [entry]
    house = (await client.get("/api/v1/house", auth=auth)).json()
    assert {"put_in", "shares", "set_aside"}.isdisjoint(house["example_sections"])
    assert house["asset"]["name"] == "Home"
    # The credit is excluded, so it sits in no pot.
    set_aside = house["set_aside"]
    assert (set_aside["total"], set_aside["bank_balance"]) == (0.0, 1234.56)
    assert (set_aside["bank_balance_as_of"], set_aside["difference"]) == (
        "2026-10-01",
        1234.56,
    )
    assert [(s["capital"], s["percent"]) for s in house["shares"]["now"]] == [
        (700.0, 70.0),
        (300.0, 30.0),
    ]
    assert [k["kind"] for k in house["put_in"]["kinds"]] == ["closing"]
    assert [t["amount"] for t in house["put_in"]["totals"]] == [700.0, 300.0]
    assert (
        house["shares"]["history"][0]["year"],
        house["shares"]["history"][0]["month"],
    ) == (2026, 1)

    deleted = await client.delete(
        f"/api/v1/house/manual-entries/{entry['id']}", auth=auth
    )

    assert deleted.json() == {"deleted": True}
    house = (await client.get("/api/v1/house", auth=auth)).json()
    assert [s["capital"] for s in house["shares"]["now"]] == [0.0, 0.0]
    assert (await client.get("/api/v1/house/manual-entries", auth=auth)).json() == []


async def test_a_tagged_import_credits_its_payer(client: AsyncClient) -> None:
    """US-HOUSE-10: a personal `s100` row credits the payer in full; an
    untagged split credits nothing."""
    persons, auth = await setup_and_login(client)
    await upload_csv(
        client,
        persons[0]["id"],
        HEADER
        + '2026-02-01,Insurer,Insurance,Chase,INSURER,,"-1200.00",'
        + '"s100, share:loan-interest"\n'
        + '2026-02-02,Utility,Utilities,Chase,UTILITY,,"-80.00",shared\n',
        auth=auth,
    )
    await client.put("/api/v1/house/asset", json=ASSET_BODY, auth=auth)

    house = (await client.get("/api/v1/house", auth=auth)).json()

    assert [(s["capital"], s["percent"]) for s in house["shares"]["now"]] == [
        (1200.0, 100.0),
        (0.0, 0.0),
    ]


async def test_recording_a_credit_is_validated(client: AsyncClient) -> None:
    persons, auth = await setup_and_login(client)

    for change in (
        {"share_kind": "none"},  # the schema's type
        {"amount": 0},  # the command
        {"owner_shares": {persons[0]["id"]: 70, str(UUID(int=7)): 30}},  # use case
    ):
        response = await client.post(
            "/api/v1/house/manual-entries", json=_credit(persons, **change), auth=auth
        )
        assert response.status_code == 422, change


async def test_only_a_hand_entered_row_can_be_deleted(client: AsyncClient) -> None:
    persons, auth = await setup_and_login(client)
    await upload_csv(client, persons[0]["id"], POTS_CSV, auth=auth)
    rows = (
        await client.get(
            "/api/v1/reconciliation",
            params={"year": 2026, "month": 1, "scope": "all"},
            auth=auth,
        )
    ).json()["transactions"]

    imported = await client.delete(
        f"/api/v1/house/manual-entries/{rows[0]['id']}", auth=auth
    )
    missing = await client.delete(
        f"/api/v1/house/manual-entries/{UUID(int=9)}", auth=auth
    )

    assert imported.status_code == 422
    assert missing.status_code == 404


async def test_a_recorded_credit_moves_no_settlement_budget_or_upload_figure(
    client: AsyncClient,
) -> None:
    """THE PIN (US-HOUSE-11): Settle Up, the budgets, the dashboard,
    reconciliation, and Upload history read the same before and after a
    credit is recorded in a month the other partner never uploaded."""
    persons, alice = await setup_and_login(client)
    bob = await login_as_bob(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=alice)
    month = {"year": 2026, "month": 1}
    reads = [
        ("/api/v1/settle-up", month),
        ("/api/v1/budgets/overview", month),
        ("/api/v1/budgets/overview", {**month, "scope": "personal"}),
        ("/api/v1/dashboard", month),
        ("/api/v1/reconciliation", month),
        ("/api/v1/uploads/history", {}),
    ]

    async def snapshot() -> list[dict]:
        return [
            (await client.get(path, params=params, auth=bob)).json()
            for path, params in reads
        ]

    before = await snapshot()
    posted = await client.post(
        "/api/v1/house/manual-entries", json=_credit(persons), auth=bob
    )
    assert posted.status_code == 201, posted.text

    assert await snapshot() == before
    assert "No upload from Bob" in before[0]["finalization_warnings"]


async def test_the_hand_entered_account_stays_joint_and_out_of_imports(
    client: AsyncClient,
) -> None:
    """US-HOUSE-11: unmarking and marking refuse the hand-entered account,
    and a Monarch account of the same name imports as the uploader's own."""
    persons, auth = await setup_and_login(client)
    posted = await client.post(
        "/api/v1/house/manual-entries", json=_credit(persons), auth=auth
    )
    assert posted.status_code == 201, posted.text

    unmarked = await client.delete("/api/v1/settings/accounts/joint/Escrow", auth=auth)
    marked = await client.post(
        "/api/v1/settings/accounts/joint", json={"label": "Escrow"}, auth=auth
    )
    await upload_csv(
        client,
        persons[0]["id"],
        HEADER + '2026-02-03,Title Co,Fees,Escrow,TITLE CO,,"-75.00",\n',
        auth=auth,
    )

    assert unmarked.status_code == 422
    assert "hand-entered" in unmarked.json()["error"]["message"]
    assert marked.status_code == 422
    accounts = (await client.get("/api/v1/settings/accounts", auth=auth)).json()
    assert sorted(
        (a["name"], a["kind"], a["owner_person_id"]) for a in accounts["accounts"]
    ) == [("Escrow", "joint", None), ("Escrow", "personal", persons[0]["id"])]
    listed = (await client.get("/api/v1/house/manual-entries", auth=auth)).json()
    assert [e["id"] for e in listed] == [posted.json()["id"]]
