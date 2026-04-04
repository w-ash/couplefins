import pytest

from tests.fixtures.factories import make_settlement_merchant


def test_valid_merchant() -> None:
    m = make_settlement_merchant(name="Venmo", merchant_pattern="venmo")
    assert m.name == "Venmo"
    assert m.merchant_pattern == "venmo"


def test_short_pattern_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        make_settlement_merchant(merchant_pattern="v")


def test_minimum_pattern_accepted() -> None:
    m = make_settlement_merchant(merchant_pattern="vz")
    assert m.merchant_pattern == "vz"


def test_empty_name_raises() -> None:
    with pytest.raises(ValueError, match="name must not be empty"):
        make_settlement_merchant(name="")


def test_whitespace_name_raises() -> None:
    with pytest.raises(ValueError, match="name must not be empty"):
        make_settlement_merchant(name="   ")
