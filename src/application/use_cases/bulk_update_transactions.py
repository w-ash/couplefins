from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from attrs import define, evolve, field

from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import ValidationError
from src.domain.formatting import FieldValue
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.finalization import assert_period_not_finalized
from ._shared.transaction_pipeline import (
    compute_edit,
    fetch_and_validate,
    validate_payer_percentage,
)

if TYPE_CHECKING:
    from src.domain.entities.transaction import Transaction


class Unset(Enum):
    UNSET = "UNSET"


@define(frozen=True, slots=True)
class BulkUpdateTransactionsCommand:
    transaction_ids: list[UUID]
    date: date | None = None
    amount: Decimal | None = None
    category: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] | None = None
    payer_percentage: int | Unset = field(default=Unset.UNSET)
    household: bool | Unset = field(default=Unset.UNSET)
    is_excluded: bool | Unset = field(default=Unset.UNSET)
    edited_by_person_id: UUID | None = None


@define(frozen=True, slots=True)
class BulkUpdateTransactionsResult:
    updated_transactions: list[Transaction]
    edits: list[TransactionEdit]
    updated_count: int


def _collect_updates(
    command: BulkUpdateTransactionsCommand,
) -> dict[str, FieldValue]:
    updates: dict[str, FieldValue] = {}
    if command.date is not None:
        updates["date"] = command.date
    if command.amount is not None:
        updates["amount"] = command.amount
    if command.category is not None:
        updates["category"] = command.category
    if command.notes is not None:
        updates["notes"] = command.notes
    if command.tags is not None:
        updates["tags"] = tuple(t.lower() for t in command.tags)
    if not isinstance(command.payer_percentage, Unset):
        updates["payer_percentage"] = command.payer_percentage
    if not isinstance(command.household, Unset):
        updates["household"] = command.household
    if not isinstance(command.is_excluded, Unset):
        updates["is_excluded"] = command.is_excluded
    return updates


def _preserve_originals(updates: dict[str, FieldValue], tx: Transaction) -> None:
    if "date" in updates and updates["date"] != tx.date and tx.original_date is None:
        updates["original_date"] = tx.date
    if (
        "amount" in updates
        and updates["amount"] != tx.amount
        and tx.original_amount is None
    ):
        updates["original_amount"] = tx.amount


def _validate_command(
    command: BulkUpdateTransactionsCommand,
    updates: dict[str, FieldValue],
) -> None:
    if not command.transaction_ids:
        raise ValidationError("At least one transaction ID is required")
    if not updates:
        raise ValidationError("At least one field to update is required")
    if len(command.transaction_ids) > 1 and ("date" in updates or "amount" in updates):
        raise ValidationError(
            "date and amount can only be changed for a single transaction"
        )
    if not isinstance(command.payer_percentage, Unset):
        validate_payer_percentage(command.payer_percentage)


_EDIT_FIELDS = (
    "date",
    "amount",
    "category",
    "notes",
    "tags",
    "payer_percentage",
    "household",
    "is_excluded",
)


async def apply_bulk_transaction_updates(
    command: BulkUpdateTransactionsCommand,
    uow: UnitOfWorkProtocol,
) -> BulkUpdateTransactionsResult:
    """Apply the field mutation without committing.

    Split out from `BulkUpdateTransactionsUseCase.execute` so callers
    composing multiple mutations into one atomic operation (the chat
    assistant's combined tag + field bulk update) can run this inside a
    single `async with uow:` scope and commit once at the end — see
    `src.application.chat.confirmed_actions._exec_bulk`.
    """
    updates = _collect_updates(command)
    _validate_command(command, updates)

    transactions = await fetch_and_validate(uow, command.transaction_ids)

    if "date" in updates:
        tx = transactions[command.transaction_ids[0]]
        new_date = updates["date"]
        if new_date != tx.date and isinstance(new_date, date):
            await assert_period_not_finalized(uow, new_date.year, new_date.month)

    all_edits: list[TransactionEdit] = []
    updated_transactions: list[Transaction] = []
    now = datetime.now(UTC)
    uses_immutable_fields = "date" in updates or "amount" in updates

    for tx_id in command.transaction_ids:
        tx = transactions[tx_id]
        tx_updates = dict(updates)
        _preserve_originals(tx_updates, tx)

        field_values: tuple[tuple[str, FieldValue], ...] = (
            ("date", tx.date),
            ("amount", tx.amount),
            ("category", tx.category),
            ("notes", tx.notes),
            ("tags", tx.tags),
            ("payer_percentage", tx.payer_percentage),
            ("household", tx.household),
            ("is_excluded", tx.is_excluded),
        )
        edits = [
            e
            for name, old in field_values
            if name in tx_updates
            and (
                e := compute_edit(
                    tx,
                    name,
                    old,
                    tx_updates[name],
                    now=now,
                    edited_by_person_id=command.edited_by_person_id,
                )
            )
        ]
        if not edits:
            continue

        all_edits.extend(edits)
        updated_tx: Transaction = evolve(tx, **tx_updates)
        updated_transactions.append(updated_tx)

        if uses_immutable_fields:
            await uow.transactions.update_all_fields(updated_tx)
        else:
            await uow.transactions.update_mutable_fields(updated_tx)

    if all_edits:
        await uow.transaction_edits.save_batch(all_edits)

    return BulkUpdateTransactionsResult(
        updated_transactions=updated_transactions,
        edits=all_edits,
        updated_count=len(updated_transactions),
    )


@define(slots=True)
class BulkUpdateTransactionsUseCase:
    async def execute(
        self,
        command: BulkUpdateTransactionsCommand,
        uow: UnitOfWorkProtocol,
    ) -> BulkUpdateTransactionsResult:
        async with uow:
            result = await apply_bulk_transaction_updates(command, uow)
            await uow.commit()
            return result
