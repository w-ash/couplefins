from decimal import Decimal

from src.domain.splits import compute_shares


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
