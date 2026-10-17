from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from attrs import define, evolve

from src.domain.entities.transaction import Transaction
from src.domain.formatting import field_str as _field_str
from src.domain.tags import merge_namespaced_tags


@define(frozen=True, slots=True)
class TransactionNaturalKey:
    """A row's identity across imports. The account id names the owner too:
    a personal account derives from its owner and label, a joint account
    from its label alone, so both owners' exports of a joint row share a key."""

    date: date
    amount: Decimal
    account_id: UUID
    original_statement: str
    occurrence: int


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
    # `is not None`, not truthiness: a Decimal('0.00') original_amount is falsy,
    # so `or` would key an edited zero-dollar row on its current amount and
    # break the pairing with its CSV twin (misclassifying it new/removed).
    return TransactionNaturalKey(
        date=tx.original_date if tx.original_date is not None else tx.date,
        amount=tx.original_amount if tx.original_amount is not None else tx.amount,
        account_id=tx.account_id,
        original_statement=tx.original_statement,
        occurrence=tx.occurrence,
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
    Monarch and must be removed. The caller scopes `existing` to the rows
    the uploader owns in the upload's date window: their personal rows, and
    the rows of a joint account the file names that their own uploads
    imported. A partner's import of a joint row is never a removal
    candidate, nor is any row outside that scope.
    """
    incoming_keys = {natural_key(tx) for tx in incoming}
    return [tx for tx in existing if natural_key(tx) not in incoming_keys]


def classify_transactions(
    incoming: list[Transaction], existing: list[Transaction]
) -> list[ClassifiedTransaction]:
    """Pair each incoming row with its stored twin by natural key.

    A matched row keeps the stored row's namespaced tags that the source
    lacks (`merge_namespaced_tags`): an import never removes a label,
    whether it came from the source or the app. The kept tags are part of
    `incoming`, so neither the diffs nor the update that writes `incoming`
    removes them.
    """
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
            kept = evolve(tx, tags=merge_namespaced_tags(tx.tags, match.tags))
            diffs = _diff_fields(kept, match)
            results.append(
                ClassifiedTransaction(
                    incoming=kept,
                    status="changed" if diffs else "unchanged",
                    existing_id=match.id,
                    diffs=diffs,
                )
            )
    return results
