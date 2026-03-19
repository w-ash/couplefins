import pytest

from tests.fixtures.factories import make_transaction

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
