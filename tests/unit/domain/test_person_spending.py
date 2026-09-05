from decimal import Decimal
from uuid import UUID

import pytest

from src.domain.person_spending import (
    compute_person_share,
    signed_person_share,
)
from tests.fixtures.factories import ALICE, BOB, make_transaction


@pytest.mark.parametrize(
    ("amount", "payer_percentage", "viewer", "expected"),
    [
        # 50/50 household split: same share either side
        (-100, 50, ALICE.id, "50.00"),
        (-100, 50, BOB.id, "50.00"),
        # custom split: payer keeps 70%
        (-200, 70, ALICE.id, "140.00"),
        (-200, 70, BOB.id, "60.00"),
        # spotted: $0 for the payer, everything for the beneficiary
        (-30, 0, ALICE.id, "0.00"),
        (-30, 0, BOB.id, "30.00"),
        # no split: all on the payer
        (-60, 100, ALICE.id, "60.00"),
        (-60, 100, BOB.id, "0.00"),
    ],
)
def test_person_share(
    amount: int, payer_percentage: int, viewer: UUID, expected: str
) -> None:
    tx = make_transaction(
        amount=Decimal(amount),
        payer_percentage=payer_percentage,
        payer_person_id=ALICE.id,
    )
    assert compute_person_share(tx, viewer) == Decimal(expected)


def test_signed_share_expense_is_positive() -> None:
    tx = make_transaction(
        amount=Decimal(-100), payer_percentage=50, payer_person_id=ALICE.id
    )
    assert signed_person_share(tx, BOB.id) == Decimal("50.00")


def test_signed_share_refund_is_negative() -> None:
    tx = make_transaction(
        amount=Decimal(100), payer_percentage=50, payer_person_id=ALICE.id
    )
    assert signed_person_share(tx, ALICE.id) == Decimal("-50.00")
