"""`as_joint_row`: the one transform behind importing a row on a joint label
and marking a label joint (US-IMPORT-5, US-ACCOUNT-1)."""

from decimal import Decimal
from uuid import UUID

import pytest

from src.domain.entities.account import joint_account_id
from src.domain.filters import is_joint_row
from src.domain.joint import as_joint_row
from tests.fixtures.factories import ALICE, BOB, make_transaction

JOINT_ID = joint_account_id("Joint Checking")


def test_the_row_loses_its_payer_and_leaves_settlement() -> None:
    tx = make_transaction(payer_person_id=ALICE.id, household=False, is_settlement=True)

    joint = as_joint_row(
        tx, account_id=JOINT_ID, persons=(ALICE, BOB), carry_split=False
    )

    assert is_joint_row(joint)
    assert joint.account_id == JOINT_ID
    assert (joint.payer_percentage, joint.household, joint.is_settlement) == (
        100,
        True,
        False,
    )


@pytest.mark.parametrize(
    ("carry_split", "expected"), [(True, {BOB.id: 30, ALICE.id: 70}), (False, None)]
)
def test_a_hand_set_split_carries_only_when_asked(
    carry_split: bool, expected: dict[UUID, int] | None
) -> None:
    tx = make_transaction(payer_person_id=BOB.id, payer_percentage=30)

    joint = as_joint_row(
        tx, account_id=JOINT_ID, persons=(ALICE, BOB), carry_split=carry_split
    )

    assert joint.owner_shares == expected


def test_an_unsplit_row_carries_no_owner_shares() -> None:
    tx = make_transaction(payer_person_id=BOB.id, payer_percentage=100)

    joint = as_joint_row(
        tx, account_id=JOINT_ID, persons=(ALICE, BOB), carry_split=True
    )

    assert joint.owner_shares is None


@pytest.mark.parametrize(
    ("amount", "expected"), [("1500.00", BOB.id), ("-1500.00", None)]
)
def test_money_in_names_the_one_person_its_text_names(
    amount: str, expected: UUID | None
) -> None:
    tx = make_transaction(
        payer_person_id=ALICE.id,
        amount=Decimal(amount),
        original_statement="TRANSFER FROM BOB",
    )

    joint = as_joint_row(
        tx, account_id=JOINT_ID, persons=(ALICE, BOB), carry_split=True
    )

    assert joint.depositor_person_id == expected
