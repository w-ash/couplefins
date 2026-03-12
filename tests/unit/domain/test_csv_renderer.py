import csv
from datetime import date
from decimal import Decimal
import io

from src.domain.export.adjustments import Adjustment
from src.domain.export.csv_renderer import ADJUSTMENT_TAG, render_adjustment_csv


def _make_adjustment(
    *,
    dedup_id: str = "a1b2c3d4e5f6",
    dt: date = date(2026, 1, 15),
    merchant: str = "Test Merchant",
    category: str = "Dining Out",
    amount: Decimal = Decimal("-50.00"),
    account: str = "Shared Adjustments",
) -> Adjustment:
    from uuid import uuid4

    return Adjustment(
        dedup_id=dedup_id,
        source_transaction_id=uuid4(),
        date=dt,
        merchant=merchant,
        category=category,
        amount=amount,
        account=account,
    )


def test_single_adjustment_produces_header_and_row() -> None:
    adj = _make_adjustment()
    result = render_adjustment_csv([adj])
    rows = list(csv.reader(io.StringIO(result)))
    assert len(rows) == 2
    assert rows[0] == [
        "Date",
        "Amount",
        "Merchant",
        "Category",
        "Account",
        "Tags",
        "Notes",
    ]
    assert rows[1][0] == "2026-01-15"
    assert rows[1][1] == "-50.00"
    assert rows[1][2] == "Test Merchant"
    assert rows[1][3] == "Dining Out"
    assert rows[1][4] == "Shared Adjustments"
    assert rows[1][5] == ADJUSTMENT_TAG
    assert rows[1][6] == "[cf:a1b2c3d4e5f6]"


def test_empty_adjustments_produces_header_only() -> None:
    result = render_adjustment_csv([])
    rows = list(csv.reader(io.StringIO(result)))
    assert len(rows) == 1
    assert rows[0][0] == "Date"


def test_positive_amount_no_sign_prefix() -> None:
    adj = _make_adjustment(amount=Decimal("25.50"))
    result = render_adjustment_csv([adj])
    rows = list(csv.reader(io.StringIO(result)))
    assert rows[1][1] == "25.50"


def test_special_characters_in_merchant_escaped() -> None:
    adj = _make_adjustment(merchant='Joe\'s "BBQ", Grill & More')
    result = render_adjustment_csv([adj])
    # Round-trip parse to verify csv.reader handles it
    rows = list(csv.reader(io.StringIO(result)))
    assert rows[1][2] == 'Joe\'s "BBQ", Grill & More'


def test_idempotent_output() -> None:
    adjs = [
        _make_adjustment(dedup_id="aaa111bbb222"),
        _make_adjustment(dedup_id="ccc333ddd444", amount=Decimal("10.00")),
    ]
    first = render_adjustment_csv(adjs)
    second = render_adjustment_csv(adjs)
    assert first == second


def test_multiple_adjustments_preserve_order() -> None:
    adjs = [
        _make_adjustment(merchant="Zebra", dedup_id="111111111111"),
        _make_adjustment(merchant="Apple", dedup_id="222222222222"),
    ]
    result = render_adjustment_csv(adjs)
    rows = list(csv.reader(io.StringIO(result)))
    assert rows[1][2] == "Zebra"
    assert rows[2][2] == "Apple"


def test_notes_format() -> None:
    adj = _make_adjustment(dedup_id="deadbeef1234")
    result = render_adjustment_csv([adj])
    rows = list(csv.reader(io.StringIO(result)))
    assert rows[1][6] == "[cf:deadbeef1234]"
