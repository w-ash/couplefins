import pytest

from tests.fixtures.factories import make_transaction

# -- is_shared property --


def test_is_shared_when_payer_percentage_set() -> None:
    tx = make_transaction(payer_percentage=50)
    assert tx.is_shared is True


def test_is_shared_when_payer_percentage_zero() -> None:
    tx = make_transaction(payer_percentage=0)
    assert tx.is_shared is True


def test_is_shared_when_payer_percentage_100() -> None:
    tx = make_transaction(payer_percentage=100)
    assert tx.is_shared is True


def test_not_shared_when_payer_percentage_none() -> None:
    tx = make_transaction(payer_percentage=None, tags=())
    assert tx.is_shared is False


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


def test_accepts_payer_percentage_none() -> None:
    tx = make_transaction(payer_percentage=None, tags=())
    assert tx.payer_percentage is None
