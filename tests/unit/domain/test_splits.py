from decimal import Decimal
import uuid
from uuid import UUID

import pytest

from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.split_rules import check_owner_shares
from src.domain.splits import (
    compute_shares,
    owner_shares,
    person_share,
    share_amounts,
)
from tests.fixtures.factories import ALICE, BOB, COUPLE_IDS, make_transaction


def test_even_split_even_amount() -> None:
    payer, other = compute_shares(Decimal("-100.00"), 50)
    assert payer == Decimal("50.00")
    assert other == Decimal("50.00")
    assert payer + other == Decimal("100.00")


def test_even_split_odd_cent() -> None:
    payer, other = compute_shares(Decimal("-33.33"), 50)
    assert payer == Decimal("16.67")
    assert other == Decimal("16.66")
    assert payer + other == Decimal("33.33")


def test_asymmetric_split() -> None:
    payer, other = compute_shares(Decimal("-100.00"), 70)
    assert payer == Decimal("70.00")
    assert other == Decimal("30.00")
    assert payer + other == Decimal("100.00")


def test_zero_percent_split() -> None:
    payer, other = compute_shares(Decimal("-100.00"), 0)
    assert payer == Decimal("0.00")
    assert other == Decimal("100.00")
    assert payer + other == Decimal("100.00")


def test_full_percent_split() -> None:
    payer, other = compute_shares(Decimal("-100.00"), 100)
    assert payer == Decimal("100.00")
    assert other == Decimal("0.00")
    assert payer + other == Decimal("100.00")


def test_boundary_one_cent() -> None:
    payer, other = compute_shares(Decimal("-0.01"), 50)
    assert payer == Decimal("0.01")
    assert other == Decimal("0.00")
    assert payer + other == Decimal("0.01")


# --- Per-row splits: owner_shares / share_amounts / person_share ---


def _old_person_share(tx: Transaction, person_id: UUID) -> Decimal:
    """The pre-joint formula: payer gets the rounded share, partner the rest."""
    payer_share, other_share = compute_shares(tx.amount, tx.payer_percentage)
    return payer_share if tx.payer_person_id == person_id else other_share


@pytest.mark.parametrize("payer", [ALICE.id, BOB.id])
@pytest.mark.parametrize("pct", [0, 33, 50, 70, 100])
@pytest.mark.parametrize("amount", ["-33.33", "-0.01", "12.35", "-100.00"])
def test_personal_row_shares_match_the_old_formula(
    payer: UUID, pct: int, amount: str
) -> None:
    tx = make_transaction(
        payer_person_id=payer, payer_percentage=pct, amount=Decimal(amount)
    )

    for person_id in COUPLE_IDS:
        assert person_share(tx, person_id, COUPLE_IDS) == _old_person_share(
            tx, person_id
        )


def test_personal_row_owner_shares_put_the_payer_first() -> None:
    tx = make_transaction(payer_person_id=BOB.id, payer_percentage=70)

    assert list(owner_shares(tx, COUPLE_IDS).items()) == [(BOB.id, 70), (ALICE.id, 30)]


def test_joint_row_splits_evenly_and_sums_exactly_on_an_odd_cent() -> None:
    tx = make_transaction(joint=True, amount=Decimal("-33.33"))

    assert owner_shares(tx, COUPLE_IDS) == {ALICE.id: 50, BOB.id: 50}
    # The first of the couple gets the half-up cent; the two sum to the amount.
    assert share_amounts(tx, COUPLE_IDS) == {
        ALICE.id: Decimal("16.67"),
        BOB.id: Decimal("16.66"),
    }
    assert share_amounts(tx, (BOB.id, ALICE.id)) == {
        BOB.id: Decimal("16.67"),
        ALICE.id: Decimal("16.66"),
    }


def test_joint_row_override_sets_each_owners_share() -> None:
    tx = make_transaction(
        joint=True, amount=Decimal("-200.00"), owner_shares={BOB.id: 70, ALICE.id: 30}
    )

    assert owner_shares(tx, COUPLE_IDS) == {ALICE.id: 30, BOB.id: 70}
    assert person_share(tx, ALICE.id, COUPLE_IDS) == Decimal("60.00")
    assert person_share(tx, BOB.id, COUPLE_IDS) == Decimal("140.00")


@pytest.mark.parametrize("person_ids", [(), (ALICE.id,), (ALICE.id, BOB.id, ALICE.id)])
def test_a_split_needs_exactly_two_persons(person_ids: tuple[UUID, ...]) -> None:
    with pytest.raises(InvariantViolationError, match="needs 2 persons"):
        owner_shares(make_transaction(payer_person_id=ALICE.id), person_ids)


def test_a_payer_outside_the_couple_is_an_invariant_violation() -> None:
    with pytest.raises(InvariantViolationError, match="not one of the couple"):
        owner_shares(make_transaction(), COUPLE_IDS)


def test_an_override_naming_other_persons_is_an_invariant_violation() -> None:
    tx = make_transaction(joint=True, owner_shares={ALICE.id: 50, uuid.uuid4(): 50})

    with pytest.raises(InvariantViolationError, match="other persons"):
        owner_shares(tx, COUPLE_IDS)


def test_a_person_outside_the_couple_has_no_share() -> None:
    with pytest.raises(InvariantViolationError, match="not one of the couple"):
        person_share(
            make_transaction(payer_person_id=ALICE.id), uuid.uuid4(), COUPLE_IDS
        )


# --- Joint deposits: a deposit naming its depositor is theirs alone ---


def _deposit(depositor: UUID | None, amount: str = "1500.00") -> Transaction:
    return make_transaction(
        joint=True,
        amount=Decimal(amount),
        depositor_person_id=depositor,
        owner_shares={ALICE.id: 30, BOB.id: 70},
    )


@pytest.mark.parametrize("depositor", [ALICE.id, BOB.id])
def test_a_deposit_is_its_depositors_over_any_override(depositor: UUID) -> None:
    tx = _deposit(depositor)
    partner = BOB.id if depositor == ALICE.id else ALICE.id

    assert owner_shares(tx, COUPLE_IDS) == {depositor: 100, partner: 0}
    assert share_amounts(tx, COUPLE_IDS) == {
        depositor: Decimal("1500.00"),
        partner: Decimal("0.00"),
    }
    assert person_share(tx, depositor, COUPLE_IDS) == Decimal("1500.00")
    assert person_share(tx, partner, COUPLE_IDS) == Decimal("0.00")


def test_without_a_depositor_a_deposit_splits_by_its_owner_shares() -> None:
    assert owner_shares(_deposit(None), COUPLE_IDS) == {ALICE.id: 30, BOB.id: 70}


def test_a_depositor_on_a_payment_does_not_move_its_split() -> None:
    """The deposit rule is for money in: a payment keeps its owner shares."""
    tx = _deposit(ALICE.id, amount="-1500.00")

    assert owner_shares(tx, COUPLE_IDS) == {ALICE.id: 30, BOB.id: 70}


def test_a_depositor_outside_the_couple_is_an_invariant_violation() -> None:
    with pytest.raises(InvariantViolationError, match="not one of the couple"):
        owner_shares(_deposit(uuid.uuid4()), COUPLE_IDS)


@pytest.mark.parametrize(
    "tx",
    [
        make_transaction(payer_person_id=BOB.id, payer_percentage=70),
        make_transaction(joint=True, amount=Decimal("-33.33")),
        make_transaction(
            joint=True,
            amount=Decimal("-200.00"),
            owner_shares={ALICE.id: 35, BOB.id: 65},
        ),
    ],
)
def test_person_share_is_each_persons_share_amount(tx: Transaction) -> None:
    amounts = share_amounts(tx, COUPLE_IDS)

    for person_id in COUPLE_IDS:
        assert person_share(tx, person_id, COUPLE_IDS) == amounts[person_id]


def test_check_owner_shares_accepts_two_owners_summing_to_100() -> None:
    check_owner_shares({ALICE.id: 0, BOB.id: 100})
    check_owner_shares({ALICE.id: 35, BOB.id: 65}, COUPLE_IDS)


def test_check_owner_shares_rejects_owners_outside_the_couple() -> None:
    with pytest.raises(ValueError, match="each of the couple"):
        check_owner_shares({ALICE.id: 50, uuid.uuid4(): 50}, COUPLE_IDS)


@pytest.mark.parametrize(
    ("shares", "message"),
    [
        ({ALICE.id: 100}, "name 2 owners"),
        ({ALICE.id: 50, BOB.id: 30, uuid.UUID(int=1): 20}, "name 2 owners"),
        ({ALICE.id: 60, BOB.id: 60}, "sum to 100"),
        ({ALICE.id: 120, BOB.id: -20}, "payer_percentage must be 0-100"),
    ],
)
def test_check_owner_shares_rejects_bad_shares(
    shares: dict[UUID, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        check_owner_shares(shares)
