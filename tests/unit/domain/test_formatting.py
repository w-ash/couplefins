from datetime import date
from decimal import Decimal
from types import MappingProxyType

from src.domain.formatting import field_str
from tests.fixtures.factories import ALICE, BOB


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


def test_uuid_renders_as_its_string() -> None:
    assert field_str(ALICE.id) == str(ALICE.id)


def test_owner_shares_render_as_id_percent_pairs_by_id() -> None:
    shares = MappingProxyType({BOB.id: 40, ALICE.id: 60})
    assert field_str(shares) == f"{ALICE.id}:60,{BOB.id}:40"
