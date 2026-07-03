from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from attrs import define

from src.domain.entities.transaction import Transaction
from src.domain.formatting import field_str as _field_str


@define(frozen=True, slots=True)
class TransactionNaturalKey:
    date: date
    amount: Decimal
    account: str
    original_statement: str
    occurrence: int
    payer_person_id: UUID


@define(frozen=True, slots=True)
class FieldDiff:
    field_name: str
    old_value: str
    new_value: str


@define(frozen=True, slots=True)
class ClassifiedTransaction:
    incoming: Transaction
    status: Literal["new", "unchanged", "changed"]
    existing_id: UUID | None
    diffs: tuple[FieldDiff, ...]


_MUTABLE_FIELDS = (
    "merchant",
    "category",
    "notes",
    "tags",
    "payer_percentage",
    "household",
)


def natural_key(tx: Transaction) -> TransactionNaturalKey:
    return TransactionNaturalKey(
        date=tx.original_date or tx.date,
        amount=tx.original_amount or tx.amount,
        account=tx.account,
        original_statement=tx.original_statement,
        occurrence=tx.occurrence,
        payer_person_id=tx.payer_person_id,
    )


def _mutable_fields(tx: Transaction) -> dict[str, str | int | tuple[str, ...] | None]:
    return {f: getattr(tx, f) for f in _MUTABLE_FIELDS}


def _diff_fields(incoming: Transaction, existing: Transaction) -> tuple[FieldDiff, ...]:
    incoming_fields = _mutable_fields(incoming)
    existing_fields = _mutable_fields(existing)
    return tuple(
        FieldDiff(
            field_name=name,
            old_value=_field_str(existing_fields[name]),
            new_value=_field_str(incoming_fields[name]),
        )
        for name in incoming_fields
        if incoming_fields[name] != existing_fields[name]
    )


def find_removed_transactions(
    incoming: list[Transaction], existing: list[Transaction]
) -> list[Transaction]:
    """Existing rows whose natural key no longer appears in the incoming CSV.

    Re-upload is a true replace: these rows were deleted (or re-keyed) in
    Monarch and must be removed. The caller guarantees `existing` is scoped
    to the uploader's own rows within the upload's date window — rows outside
    that window are never removal candidates.
    """
    incoming_keys = {natural_key(tx) for tx in incoming}
    return [tx for tx in existing if natural_key(tx) not in incoming_keys]


def classify_transactions(
    incoming: list[Transaction], existing: list[Transaction]
) -> list[ClassifiedTransaction]:
    existing_by_key = {natural_key(tx): tx for tx in existing}
    results: list[ClassifiedTransaction] = []
    for tx in incoming:
        key = natural_key(tx)
        match = existing_by_key.get(key)
        if match is None:
            results.append(
                ClassifiedTransaction(
                    incoming=tx, status="new", existing_id=None, diffs=()
                )
            )
        else:
            diffs = _diff_fields(tx, match)
            results.append(
                ClassifiedTransaction(
                    incoming=tx,
                    status="changed" if diffs else "unchanged",
                    existing_id=match.id,
                    diffs=diffs,
                )
            )
    return results
