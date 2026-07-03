import collections
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import uuid

from src.domain.constants import (
    RESERVED_TAGS,
    HouseholdTags,
    SettlementTags,
    SharedTags,
    SplitDefaults,
)
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import ValidationError

REQUIRED_COLUMNS = {
    "Date",
    "Merchant",
    "Category",
    "Account",
    "Original Statement",
    "Notes",
    "Amount",
    "Tags",
}

MAX_ROW_ERRORS = 25


def parse_monarch_csv(
    csv_text: str,
    payer_person_id: uuid.UUID,
    upload_id: uuid.UUID,
    *,
    person_names: frozenset[str] = frozenset(),
) -> list[Transaction]:
    reader = csv.DictReader(io.StringIO(csv_text))

    if reader.fieldnames is None:
        raise ValidationError("CSV is empty or has no headers")

    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValidationError(
            f"CSV missing required columns: {', '.join(sorted(missing))}"
        )

    occurrence_counter: collections.Counter[tuple[date, Decimal, str, str]] = (
        collections.Counter()
    )
    transactions: list[Transaction] = []
    errors: list[str] = []
    for row_num, row in enumerate(reader, start=2):
        tags = _parse_tags(row["Tags"])
        is_settlement = _is_settlement(tags)

        if is_settlement:
            household = False
            payer_percentage = 100
        else:
            household, payer_percentage = _classify(tags, person_names)

        try:
            amount = Decimal(row["Amount"])
        except InvalidOperation, ValueError:
            errors.append(
                f'Row {row_num} ({row["Merchant"]}): invalid amount "{row["Amount"]}"'
            )
            continue

        try:
            tx_date = date.fromisoformat(row["Date"])
        except ValueError:
            errors.append(
                f'Row {row_num} ({row["Merchant"]}): invalid date "{row["Date"]}"'
            )
            continue

        base_key = (tx_date, amount, row["Account"], row["Original Statement"])
        occurrence = occurrence_counter[base_key]
        occurrence_counter[base_key] += 1

        transactions.append(
            Transaction(
                id=uuid.uuid4(),
                upload_id=upload_id,
                date=tx_date,
                merchant=row["Merchant"],
                category=row["Category"],
                account=row["Account"],
                original_statement=row["Original Statement"],
                occurrence=occurrence,
                notes=row["Notes"],
                amount=amount,
                tags=tags,
                payer_person_id=payer_person_id,
                payer_percentage=payer_percentage,
                household=household,
                is_settlement=is_settlement,
            )
        )

    if errors:
        displayed = errors[:MAX_ROW_ERRORS]
        if len(errors) > MAX_ROW_ERRORS:
            displayed.append(f"...and {len(errors) - MAX_ROW_ERRORS} more")
        raise ValidationError("\n".join(displayed))

    return transactions


def _parse_tags(tags_str: str) -> tuple[str, ...]:
    if not tags_str or not tags_str.strip():
        return ()
    return tuple(tag.strip().lower() for tag in tags_str.split(",") if tag.strip())


def _is_settlement(tags: tuple[str, ...]) -> bool:
    return any(tag.lower() in SettlementTags.TAGS for tag in tags)


def _classify(tags: tuple[str, ...], person_names: frozenset[str]) -> tuple[bool, int]:
    """Classify a transaction from its tags into (household, payer_percentage).

    household is set by shared/split or household tags — budget relevance.
    sXX is authoritative for payer_percentage in every tag combination — it
    overrides the defaults implied by shared, household, or person-name tags.
    Person-name tags set payer_percentage=0 (spotted) but do NOT imply
    household — a spotted expense is the beneficiary's personal spending.
    """
    lower_tags = [tag.lower() for tag in tags]

    explicit_split = _extract_max_split_percentage(lower_tags)
    has_shared = any(t in SharedTags.TAGS for t in lower_tags)
    has_household = any(t in HouseholdTags.TAGS for t in lower_tags)
    has_person_name = _has_person_name_tag(lower_tags, person_names)

    household = has_shared or has_household

    if explicit_split is not None:
        return household, explicit_split

    if has_person_name:
        return household, 0

    if has_shared:
        return True, SplitDefaults.DEFAULT_PAYER_PERCENTAGE

    if has_household:
        return True, 100

    return False, 100


def _extract_max_split_percentage(lower_tags: list[str]) -> int | None:
    """Return the max sXX value from tags, or None if no valid sXX tags."""
    values: list[int] = []
    for tag in lower_tags:
        match = SharedTags.SPLIT_TAG_PATTERN.match(tag)
        if match:
            value = int(match.group(1))
            if 0 <= value <= SplitDefaults.MAX_PAYER_PERCENTAGE:
                values.append(value)
    return max(values) if values else None


def _has_person_name_tag(lower_tags: list[str], person_names: frozenset[str]) -> bool:
    """Check if any tag matches a known person name (excluding reserved tags)."""
    if not person_names:
        return False
    return any(t in person_names and t not in RESERVED_TAGS for t in lower_tags)
