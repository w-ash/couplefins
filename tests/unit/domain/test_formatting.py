from datetime import date
from decimal import Decimal

from src.domain.formatting import field_str


def test_str_value() -> None:
    assert field_str("hello") == "hello"


def test_int_value() -> None:
    assert field_str(50) == "50"


def test_none_value() -> None:
    assert not field_str(None)


def test_date_value() -> None:
    assert field_str(date(2026, 1, 15)) == "2026-01-15"


def test_decimal_value() -> None:
    assert field_str(Decimal("-50.00")) == "-50.00"


def test_tuple_value() -> None:
    assert field_str(("shared", "s70")) == "shared,s70"


def test_empty_tuple() -> None:
    assert not field_str(())
