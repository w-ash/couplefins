import operator

from attrs import evolve
import pytest

from tests.fixtures.factories import ALICE, BOB, make_transaction

# -- household field --


def test_household_default_false() -> None:
    tx = make_transaction(household=False)
    assert tx.household is False


def test_household_field_stored() -> None:
    tx = make_transaction(household=True)
    assert tx.household is True


# -- payer_percentage defaults --


def test_payer_percentage_default_100() -> None:
    tx = make_transaction(payer_percentage=100, household=False)
    assert tx.payer_percentage == 100


# -- payer_percentage validation --


def test_rejects_payer_percentage_over_100() -> None:
    with pytest.raises(ValueError, match="payer_percentage must be 0-100, got 150"):
        make_transaction(payer_percentage=150)


def test_rejects_negative_payer_percentage() -> None:
    with pytest.raises(ValueError, match="payer_percentage must be 0-100, got -1"):
        make_transaction(payer_percentage=-1)


def test_accepts_payer_percentage_boundary_0() -> None:
    tx = make_transaction(payer_percentage=0)
    assert tx.payer_percentage == 0


def test_accepts_payer_percentage_boundary_100() -> None:
    tx = make_transaction(payer_percentage=100)
    assert tx.payer_percentage == 100


# -- joint rows --


def test_joint_row_has_no_payer() -> None:
    tx = make_transaction(joint=True)
    assert tx.payer_person_id is None


def test_joint_row_carries_owner_shares_and_a_depositor() -> None:
    tx = make_transaction(
        joint=True,
        owner_shares={ALICE.id: 40, BOB.id: 60},
        depositor_person_id=ALICE.id,
    )
    assert tx.owner_shares == {ALICE.id: 40, BOB.id: 60}
    assert tx.depositor_person_id == ALICE.id


def test_owner_shares_are_read_only_and_copied() -> None:
    shares = {ALICE.id: 40, BOB.id: 60}
    tx = make_transaction(joint=True, owner_shares=shares)
    shares[ALICE.id] = 0

    assert tx.owner_shares == {ALICE.id: 40, BOB.id: 60}
    with pytest.raises(TypeError):
        operator.setitem(tx.owner_shares, ALICE.id, 0)


def test_joint_row_with_owner_shares_stays_hashable_and_comparable() -> None:
    tx = make_transaction(joint=True, owner_shares={ALICE.id: 40, BOB.id: 60})

    assert hash(tx) == hash(evolve(tx))
    assert tx == evolve(tx)
    assert tx != evolve(tx, owner_shares={ALICE.id: 50, BOB.id: 50})


def test_rejects_owner_shares_on_a_personal_row() -> None:
    with pytest.raises(ValueError, match="Only a joint row"):
        make_transaction(owner_shares={ALICE.id: 50, BOB.id: 50})


def test_rejects_a_depositor_on_a_personal_row() -> None:
    with pytest.raises(ValueError, match="Only a joint row"):
        make_transaction(depositor_person_id=ALICE.id)


def test_rejects_owner_shares_not_summing_to_100() -> None:
    with pytest.raises(ValueError, match="sum to 100"):
        make_transaction(joint=True, owner_shares={ALICE.id: 50, BOB.id: 40})
