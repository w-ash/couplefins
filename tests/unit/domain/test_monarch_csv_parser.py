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


def test_standard_household_expense_fifty_fifty() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    tx = result[0]
    assert tx.household is True
    assert tx.payer_percentage == 50
    assert tx.tags == ("shared",)


def test_non_household_expense() -> None:
    csv = _make_csv({"Tags": "personal"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    tx = result[0]
    assert tx.household is False
    assert tx.payer_percentage == 100


def test_s70_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s70"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 70


def test_s100_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s100"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 100


def test_s0_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s0"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 0


def test_s33_tag_sets_payer_percentage() -> None:
    csv = _make_csv({"Tags": "shared, s33"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 33


def test_case_insensitive_shared_tag() -> None:
    for tag in ("Shared", "SHARED", "Split", "SPLIT"):
        csv = _make_csv({"Tags": tag})
        result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions
        assert result[0].household is True, (
            f"Tag '{tag}' should be recognized as shared"
        )


def test_empty_tags_is_personal() -> None:
    csv = _make_csv({"Tags": ""})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].household is False
    assert result[0].payer_percentage == 100


def test_negative_amount_is_expense() -> None:
    csv = _make_csv({"Amount": "-100.50", "Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert result[0].amount == Decimal("-100.50")


def test_positive_amount_is_income_refund() -> None:
    csv = _make_csv({"Amount": "25.00", "Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert result[0].amount == Decimal("25.00")


def test_multiple_rows_returns_correct_count() -> None:
    csv = _make_csv(
        {"Merchant": "Store A", "Tags": "shared"},
        {"Merchant": "Store B", "Tags": "shared"},
        {"Merchant": "Store C", "Tags": ""},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 3


def test_header_only_csv_returns_empty_list() -> None:
    csv = "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags"
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert result == []


def test_missing_required_columns_raises_validation_error() -> None:
    csv = "Date,Merchant,Amount\n2026-01-15,Test,-50.00"
    with pytest.raises(ValidationError, match="missing required columns"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_payer_person_id_comes_from_parameter() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert result[0].payer_person_id == PAYER_ID


def test_upload_id_comes_from_parameter() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert result[0].upload_id == UPLOAD_ID


def test_invalid_sxx_over_100_defaults_to_50() -> None:
    csv = _make_csv({"Tags": "shared, s150"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 50


def test_occurrence_assigned_for_duplicate_natural_keys() -> None:
    csv = _make_csv(
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
        {"Original Statement": "COFFEE SHOP", "Merchant": "Coffee"},
        {"Original Statement": "CLIPPER TRANSIT FARE", "Merchant": "Clipper"},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

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
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert all(tx.occurrence == 0 for tx in result)


def test_single_invalid_amount_includes_row_number() -> None:
    csv = _make_csv({"Amount": "abc", "Merchant": "Starbucks"})
    with pytest.raises(ValidationError, match=r"Row 2 \(Starbucks\).*invalid amount"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_single_invalid_date_includes_row_number() -> None:
    csv = _make_csv({"Date": "not-a-date", "Merchant": "Target"})
    with pytest.raises(ValidationError, match=r"Row 2 \(Target\).*invalid date"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_multiple_invalid_rows_collects_all_errors() -> None:
    csv = _make_csv(
        {"Amount": "12.3.4", "Merchant": "Starbucks"},
        {"Amount": "-25.00"},  # valid row
        {"Date": "2026-13-01", "Merchant": "Amazon"},
    )
    with pytest.raises(ValidationError) as exc_info:
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    message = str(exc_info.value)
    assert "Row 2 (Starbucks)" in message
    assert "Row 4 (Amazon)" in message
    assert "invalid amount" in message
    assert "invalid date" in message
    # Two error lines
    assert len(message.split("\n")) == 2


def test_error_cap_at_max_row_errors() -> None:
    from src.domain.parsing.monarch_csv import MAX_ROW_ERRORS

    rows = [{"Amount": "bad", "Merchant": f"Store{i}"} for i in range(30)]
    csv = _make_csv(*rows)
    with pytest.raises(ValidationError) as exc_info:
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    message = str(exc_info.value)
    lines = message.split("\n")
    # 25 error lines + 1 "...and N more" line
    assert len(lines) == MAX_ROW_ERRORS + 1
    assert "...and 5 more" in lines[-1]


def test_nan_amount_is_row_error() -> None:
    csv = _make_csv({"Amount": "NaN", "Merchant": "Starbucks"})
    with pytest.raises(
        ValidationError, match=r"Row 2 \(Starbucks\).*non-finite amount"
    ):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_infinity_amount_is_row_error() -> None:
    for raw in ("Infinity", "-Infinity", "inf"):
        csv = _make_csv({"Amount": raw, "Merchant": "Target"})
        with pytest.raises(
            ValidationError, match=r"Row 2 \(Target\).*non-finite amount"
        ):
            parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_truncated_row_is_row_error_not_typeerror() -> None:
    # Fewer columns than headers — csv.DictReader fills the rest with None.
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Starbucks\n"
    )
    with pytest.raises(ValidationError, match=r"Row 2 \(Starbucks\).*invalid amount"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_truncated_row_without_merchant_uses_placeholder() -> None:
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15\n"
    )
    with pytest.raises(ValidationError, match=r"Row 2 \(\?\).*invalid amount"):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_non_finite_and_truncated_errors_batch_together() -> None:
    csv = (
        "Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags\n"
        "2026-01-15,Starbucks,Dining Out,Chase,STARBUCKS,,NaN,\n"
        '2026-01-16,Valid,Dining Out,Chase,VALID,,"-25.00",\n'
        "2026-01-17,Amazon\n"
    )
    with pytest.raises(ValidationError) as exc_info:
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    message = str(exc_info.value)
    assert "Row 2 (Starbucks)" in message
    assert "non-finite amount" in message
    assert "Row 4 (Amazon)" in message
    assert len(message.split("\n")) == 2


def test_no_partial_import_when_errors_exist() -> None:
    csv = _make_csv(
        {"Amount": "-25.00", "Merchant": "Valid"},
        {"Amount": "bad", "Merchant": "Invalid"},
    )
    with pytest.raises(ValidationError):
        parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)


def test_household_tag_sets_household_no_split() -> None:
    csv = _make_csv({"Tags": "household"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    tx = result[0]
    assert tx.household is True
    assert tx.payer_percentage == 100


def test_person_name_tag_spotted() -> None:
    csv = _make_csv({"Tags": "bob"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"bob"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # Person-name alone = spotted (payer fronted 100%) but NOT household
    assert tx.household is False
    assert tx.payer_percentage == 0


def test_household_tag_with_sxx() -> None:
    csv = _make_csv({"Tags": "household, s30"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    tx = result[0]
    assert tx.household is True
    assert tx.payer_percentage == 30


def test_multiple_sxx_tags_highest_wins() -> None:
    csv = _make_csv({"Tags": "shared, s30, s70"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    assert result[0].payer_percentage == 70


def test_reserved_tag_not_treated_as_person_name() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"shared"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # "shared" is reserved, so it's treated as shared tag, not spotted
    assert tx.household is True
    assert tx.payer_percentage == 50


def test_sxx_alone_without_household_tag_is_personal_split() -> None:
    csv = _make_csv({"Tags": "s70"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID).transactions

    assert len(result) == 1
    tx = result[0]
    # sXX is authoritative even without a household-setting tag:
    # a personal split that enters settlement but not the household budget
    assert tx.household is False
    assert tx.payer_percentage == 70


def test_person_name_with_sxx_without_household_tag() -> None:
    csv = _make_csv({"Tags": "bob, s30"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"bob"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # sXX overrides the spotted default (0%); still personal
    assert tx.household is False
    assert tx.payer_percentage == 30


def test_household_person_name_and_sxx_uses_sxx() -> None:
    csv = _make_csv({"Tags": "household, bob, s70"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"bob"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # sXX beats the spotted default; household tag still sets budget relevance
    assert tx.household is True
    assert tx.payer_percentage == 70


def test_household_plus_person_name_is_household_spotted() -> None:
    csv = _make_csv({"Tags": "household, bob"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"bob"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # household sets budget relevance, person-name makes it spotted (0%)
    assert tx.household is True
    assert tx.payer_percentage == 0


def test_shared_tag_plus_person_name_is_household_spotted() -> None:
    csv = _make_csv({"Tags": "shared, bob"})
    result = parse_monarch_csv(
        csv, PAYER_ID, UPLOAD_ID, person_names=frozenset({"bob"})
    ).transactions

    assert len(result) == 1
    tx = result[0]
    # shared sets household, person-name makes it spotted (0%)
    assert tx.household is True
    assert tx.payer_percentage == 0


def test_adjustment_tagged_rows_are_skipped_and_counted() -> None:
    csv = _make_csv(
        {"Merchant": "Grocery Store", "Tags": "shared"},
        {"Merchant": "Adjustment", "Tags": "couplefins-adjustment"},
        {"Merchant": "Adjustment 2", "Tags": "Couplefins-Adjustment"},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert [tx.merchant for tx in result.transactions] == ["Grocery Store"]
    assert result.skipped_adjustment_count == 2


def test_adjustment_rows_skipped_before_validation() -> None:
    """A malformed re-imported adjustment row is skipped, not a row error."""
    csv = _make_csv(
        {"Merchant": "Valid", "Tags": ""},
        {"Merchant": "Adjustment", "Amount": "NaN", "Tags": "couplefins-adjustment"},
    )
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert len(result.transactions) == 1
    assert result.skipped_adjustment_count == 1


def test_no_adjustment_rows_reports_zero_skipped() -> None:
    csv = _make_csv({"Tags": "shared"})
    result = parse_monarch_csv(csv, PAYER_ID, UPLOAD_ID)

    assert result.skipped_adjustment_count == 0
