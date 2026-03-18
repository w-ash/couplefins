import collections
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import uuid

from src.domain.constants import SettlementTags, SharedTags, SplitDefaults
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
        is_shared = _is_shared(tags) and not is_settlement
        payer_percentage = _extract_split_percentage(tags) if is_shared else None

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
    return tuple(tag.strip() for tag in tags_str.split(",") if tag.strip())


def _is_shared(tags: tuple[str, ...]) -> bool:
    return any(tag.lower() in SharedTags.TAGS for tag in tags)


def _is_settlement(tags: tuple[str, ...]) -> bool:
    return any(tag.lower() in SettlementTags.TAGS for tag in tags)


def _extract_split_percentage(tags: tuple[str, ...]) -> int:
    for tag in tags:
        match = SharedTags.SPLIT_TAG_PATTERN.match(tag.lower())
        if match:
            value = int(match.group(1))
            if 0 <= value <= SplitDefaults.MAX_PAYER_PERCENTAGE:
                return value
            return SplitDefaults.DEFAULT_PAYER_PERCENTAGE
    return SplitDefaults.DEFAULT_PAYER_PERCENTAGE
