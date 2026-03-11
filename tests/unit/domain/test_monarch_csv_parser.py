import csv
from decimal import Decimal
import io
import uuid

import pytest

from src.domain.exceptions import ValidationError
from src.domain.parsing.monarch_csv import parse_monarch_csv

PAYER_ID = uuid.uuid4()
UPLOAD_ID = uuid.uuid4()

_HEADERS = [
    "Date",
    "Merchant",
    "Category",
    "Account",
    "Original Statement",
    "Notes",
    "Amount",
    "Tags",
]


def _make_csv(*rows: dict[str, str]) -> str:
    defaults = {
        "Date": "2026-01-15",
        "Merchant": "Test Merchant",
        "Category": "Dining Out",
        "Account": "Chase",
        "Original Statement": "TEST",
        "Notes": "",
        "Amount": "-50.00",
        "Tags": "",
    }
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADERS)
    for row in rows:
        merged = {**defaults, **row}
        writer.writerow([merged[h] for h in _HEADERS])
    return buf.getvalue()


def test_standard_shared_expense_fifty_fifty() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    tx = result[0]
    assert tx.is_shared is True
    assert tx.payer_percentage == 50
    assert tx.tags == ("shared",)


def test_non_shared_expense() -> None:
    csv = _make_csv({"Tags": "personal"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    tx = result[0]
    assert tx.is_shared is False
    assert tx.payer_percentage is None


def test_s70_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s70"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].payer_percentage == 70


def test_s100_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s100"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].payer_percentage == 100


def test_s0_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s0"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].payer_percentage == 0


def test_s33_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s33"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].payer_percentage == 33


def test_case_insensitive_shared_tag() -> None:
    for tag in ("Shared", "SHARED", "Split", "SPLIT"):
        csv = _make_csv({"Tags": tag})
        result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)
        assert result[0].is_shared is True, (
            f"Tag '{tag}' should be recognized as shared"
        )


def test_empty_tags_is_personal() -> None:
    csv = _make_csv({"Tags": ""})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].is_shared is False
    assert result[0].payer_percentage is None


def test_negative_amount_is_expense() -> None:
    csv = _make_csv({"Amount": "-100.50", "Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result[0].amount == Decimal("-100.50")


def test_positive_amount_is_income_refund() -> None:
    csv = _make_csv({"Amount": "25.00", "Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result[0].amount == Decimal("25.00")


def test_multiple_rows_returns_correct_count() -> None:
    csv = _make_csv(
        {"Merchant": "Store A", "Tags": "shared"},
        {"Merchant": "Store B", "Tags": "shared"},
        {"Merchant": "Store C", "Tags": ""},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 3


def test_header_only_csv_returns_empty_list() -> None:
    csv = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags"
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result == []


def test_missing_required_columns_raises_validation_error() -> None:
    csv = "Date,Merchant,Amount\n2026-01-15,Test,-50.00"
    with pytest.raises(ValidationError, match="missing required columns"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_payer_person_id_comes_from_parameter() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result[0].payer_person_id == PAYER_ID


def test_upload_id_comes_from_parameter() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result[0].upload_id == UPLOAD_ID


def test_invalid_sxx_over_100_defaults_to_50() -> None:
    csv = _make_csv({"Tags": "shared, s150"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 1
    assert result[0].payer_percentage == 50


def test_occurrence_assigned_for_duplicate_natural_keys() -> None:
    csv = _make_csv(
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
        {"Original Statement": "COFFEE SHOP", "Merchant": "Coffee"},
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result) == 4
    # First two Clipper rows + third share the same base key (same date/amount/account/stmt)
    assert result[0].occurrence == 0
    assert result[1].occurrence == 1
    assert result[2].occurrence == 0  # Different statement → own group
    assert result[3].occurrence == 2


def test_unique_rows_all_get_occurrence_zero() -> None:
    csv = _make_csv(
        {"Original Statement": "STORE A"},
        {"Original Statement": "STORE B"},
        {"Original Statement": "STORE C"},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert all(tx.occurrence == 0 for tx in result)
