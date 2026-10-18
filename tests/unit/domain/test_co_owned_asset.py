from decimal import Decimal

import pytest

from src.domain.entities.co_owned_asset import CONTRIBUTION_KINDS, ordered_kinds
from tests.fixtures.factories import make_co_owned_asset


def test_none_is_no_contribution_kind() -> None:
    """`share:none` says a row adds nothing; it never qualifies."""
    assert "none" not in CONTRIBUTION_KINDS


def test_ordered_kinds_follow_the_contribution_kinds_once_each() -> None:
    assert ordered_kinds(["repair", "closing", "repair"]) == ["closing", "repair"]
    assert ordered_kinds(frozenset()) == []


def test_a_repair_threshold_may_be_zero() -> None:
    assert make_co_owned_asset(repair_threshold=Decimal(0)).repair_threshold == 0


def test_a_repair_threshold_must_not_be_negative() -> None:
    with pytest.raises(ValueError, match="repair_threshold"):
        make_co_owned_asset(repair_threshold=Decimal("-0.01"))
