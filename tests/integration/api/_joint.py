"""Both partners' exports of one joint bank account, for the joint-account
route tests (v1.15.2)."""

from attrs import define
from httpx import AsyncClient

from tests.integration.conftest import (
    CookieAuth,
    login_as_bob,
    setup_and_login,
    upload_csv,
)

JOINT_LABEL = "Joint Checking"
HEADER = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
# Alice's export: a split dinner on her own card, and two joint rows (the
# hardware bill she tagged shared, and a deposit naming her).
ALICE_CSV = (
    HEADER
    + '2026-01-10,Restaurant,Restaurants & Bars,Chase,RESTAURANT,,"-80.00",shared\n'
    + "2026-01-12,Hardware Store,Home Improvement,Joint Checking,"
    + 'HARDWARE STORE,,"-120.00",shared\n'
    + "2026-01-14,Transfer From Alice,Transfer,Joint Checking,"
    + 'TRANSFER FROM ALICE,,"1500.00",\n'
)
# Bob's export of the same joint account, over a later window: the hardware
# bill (untagged) and the deposit again, and a grocery run after Alice's
# export ends.
BOB_CSV = (
    HEADER
    + "2026-01-12,Hardware Store,Home Improvement,Joint Checking,"
    + 'HARDWARE STORE,,"-120.00",\n'
    + "2026-01-14,Transfer From Alice,Transfer,Joint Checking,"
    + 'TRANSFER FROM ALICE,,"1500.00",\n'
    + '2026-01-20,Grocery Store,Groceries,Joint Checking,GROCERY STORE,,"-60.00",\n'
)


@define(frozen=True, slots=True)
class Couple:
    alice_id: str
    bob_id: str
    alice: CookieAuth
    bob: CookieAuth


async def couple_with_joint_exports(client: AsyncClient) -> Couple:
    """Both partners log in and upload their exports; Alice's is older."""
    persons, alice = await setup_and_login(client)
    bob = await login_as_bob(client)
    await upload_csv(client, persons[0]["id"], ALICE_CSV, auth=alice)
    await upload_csv(client, persons[1]["id"], BOB_CSV, auth=bob)
    return Couple(persons[0]["id"], persons[1]["id"], alice, bob)


async def mark_joint(client: AsyncClient, auth: CookieAuth) -> dict:
    response = await client.post(
        "/api/v1/settings/accounts/joint", json={"label": JOINT_LABEL}, auth=auth
    )
    assert response.status_code == 201, response.text
    return response.json()


async def january(client: AsyncClient, auth: CookieAuth) -> dict:
    """January's household reconciliation: rows and the settlement owed."""
    response = await client.get(
        "/api/v1/reconciliation", params={"year": 2026, "month": 1}, auth=auth
    )
    assert response.status_code == 200
    return response.json()
