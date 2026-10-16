"""US-ACCOUNT-1: marking an account label joint in Settings → Accounts."""

from httpx import AsyncClient
import pytest

from tests.integration.api._joint import (
    JOINT_LABEL,
    couple_with_joint_exports,
    january,
    mark_joint,
)
from tests.integration.conftest import CookieAuth, setup_couple

_JOINT_PATH = "/api/v1/settings/accounts/joint"


async def _accounts(
    client: AsyncClient, auth: CookieAuth
) -> list[tuple[str, str, str | None]]:
    response = await client.get("/api/v1/settings/accounts", auth=auth)
    assert response.status_code == 200
    return [
        (a["name"], a["kind"], a["owner_person_id"])
        for a in response.json()["accounts"]
    ]


async def test_lists_each_label_seen_in_uploads(client: AsyncClient) -> None:
    couple = await couple_with_joint_exports(client)

    accounts = await _accounts(client, couple.alice)

    assert sorted(accounts, key=str) == sorted(
        [
            ("Chase", "personal", couple.alice_id),
            (JOINT_LABEL, "personal", couple.alice_id),
            (JOINT_LABEL, "personal", couple.bob_id),
        ],
        key=str,
    )


async def test_marking_moves_both_partners_rows_out_of_settlement(
    client: AsyncClient,
) -> None:
    couple = await couple_with_joint_exports(client)
    before = await january(client, couple.alice)
    # Bob owes Alice half the dinner and half the hardware bill.
    assert before["settlement"]["amount"] == pytest.approx(100.0)
    alices_hardware = next(
        tx["id"]
        for tx in before["transactions"]
        if tx["merchant"] == "Hardware Store"
        and tx["payer_person_id"] == couple.alice_id
    )

    body = await mark_joint(client, couple.bob)

    assert body["account"]["kind"] == "joint"
    assert body["account"]["owner_person_id"] is None
    # Bob's copies of the hardware bill and the deposit collapse into
    # Alice's older ones.
    assert (body["moved_count"], body["dropped_count"]) == (3, 2)
    after = await january(client, couple.alice)
    # Only the dinner on Alice's own card is still split.
    assert after["settlement"]["amount"] == pytest.approx(40.0)
    assert after["settlement"]["from_person_id"] == couple.bob_id
    joint = {tx["merchant"]: tx for tx in after["transactions"] if tx["is_joint"]}
    assert set(joint) == {"Hardware Store", "Transfer From Alice", "Grocery Store"}
    assert joint["Hardware Store"]["id"] == alices_hardware
    assert joint["Hardware Store"]["payer_person_id"] is None
    # Alice's hand-set 50/50 split carries into the owner shares.
    assert joint["Hardware Store"]["owner_shares"] == {
        couple.alice_id: 50,
        couple.bob_id: 50,
    }
    assert joint["Grocery Store"]["owner_shares"] is None
    # Marking names a deposit's depositor, as importing does.
    assert joint["Transfer From Alice"]["depositor_person_id"] == couple.alice_id
    assert await _accounts(client, couple.alice) == [
        ("Chase", "personal", couple.alice_id),
        (JOINT_LABEL, "joint", None),
    ]

    settle_up = await client.get(
        "/api/v1/settle-up", params={"year": 2026, "month": 1}, auth=couple.alice
    )
    [jan] = [
        m for m in settle_up.json()["months"] if (m["year"], m["month"]) == (2026, 1)
    ]
    assert jan["balance"]["amount"] == pytest.approx(40.0)


async def test_unmarking_returns_rows_to_their_uploader(client: AsyncClient) -> None:
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)

    response = await client.delete(f"{_JOINT_PATH}/{JOINT_LABEL}", auth=couple.alice)

    assert response.status_code == 200
    assert response.json() == {"moved_count": 3}
    after = await january(client, couple.alice)
    payers = {tx["merchant"]: tx["payer_person_id"] for tx in after["transactions"]}
    assert payers["Hardware Store"] == couple.alice_id
    assert payers["Grocery Store"] == couple.bob_id
    # The hardware bill's owner shares carry back into Alice's 50/50 split.
    assert after["settlement"]["amount"] == pytest.approx(100.0)
    assert not any(tx["is_joint"] for tx in after["transactions"])


async def test_finalized_month_refuses_marking_and_unmarking(
    client: AsyncClient,
) -> None:
    couple = await couple_with_joint_exports(client)
    await mark_joint(client, couple.alice)
    finalize = await client.post(
        "/api/v1/reconciliation/finalize",
        json={"year": 2026, "month": 1},
        auth=couple.alice,
    )
    assert finalize.status_code == 200

    unmark = await client.delete(f"{_JOINT_PATH}/{JOINT_LABEL}", auth=couple.alice)
    mark = await client.post(_JOINT_PATH, json={"label": "Chase"}, auth=couple.alice)

    assert (unmark.status_code, mark.status_code) == (409, 409)


async def test_unknown_labels_are_not_found(client: AsyncClient) -> None:
    couple = await couple_with_joint_exports(client)

    mark = await client.post(_JOINT_PATH, json={"label": "Nope"}, auth=couple.alice)
    unmark = await client.delete(f"{_JOINT_PATH}/Chase", auth=couple.alice)

    assert (mark.status_code, unmark.status_code) == (404, 404)


async def test_accounts_routes_require_login(client: AsyncClient) -> None:
    await setup_couple(client)

    responses = [
        await client.get("/api/v1/settings/accounts"),
        await client.post(_JOINT_PATH, json={"label": JOINT_LABEL}),
        await client.delete(f"{_JOINT_PATH}/{JOINT_LABEL}"),
    ]

    assert [r.status_code for r in responses] == [401, 401, 401]
