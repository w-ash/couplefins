from httpx import AsyncClient
import pytest

from tests.integration.api._joint import (
    HEADER,
    JOINT_LABEL,
    couple_with_joint_exports,
    mark_joint,
)
from tests.integration.conftest import setup_and_login, setup_couple, upload_csv

_SECTIONS = ("put_in", "shares", "loans", "upcoming", "set_aside", "recent_activity")


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
