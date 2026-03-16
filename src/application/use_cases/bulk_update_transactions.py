from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from attrs import define, evolve, field

from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.finalization import assert_period_not_finalized
from ._shared.transaction_pipeline import (
    compute_edit,
    fetch_and_validate,
    validate_payer_percentage,
)

if TYPE_CHECKING:
    from src.domain.entities.transaction import Transaction

_UNSET = object()


type _FieldValue = date | Decimal | str | int | tuple[str, ...] | None


@define(frozen=True, slots=True)
class BulkUpdateTransactionsCommand:
    transaction_ids: list[UUID]
    date: date | None = None
    amount: Decimal | None = None
    category: str | None = None
    tags: tuple[str, ...] | None = None
    payer_percentage: int | object = field(default=_UNSET)


@define(frozen=True, slots=True)
class BulkUpdateTransactionsResult:
    updated_transactions: list[Transaction]
    edits: list[TransactionEdit]
    updated_count: int


def _collect_updates(
    command: BulkUpdateTransactionsCommand,
) -> dict[str, _FieldValue]:
    updates: dict[str, _FieldValue] = {}
    if command.date is not None:
        updates["date"] = command.date
    if command.amount is not None:
        updates["amount"] = command.amount
    if command.category is not None:
        updates["category"] = command.category
    if command.tags is not None:
        updates["tags"] = command.tags
    if command.payer_percentage is not _UNSET:
        updates["payer_percentage"] = command.payer_percentage  # type: ignore[assignment]
    return updates


def _preserve_originals(updates: dict[str, _FieldValue], tx: Transaction) -> None:
    if "date" in updates and updates["date"] != tx.date and tx.original_date is None:
        updates["original_date"] = tx.date
    if (
        "amount" in updates
        and updates["amount"] != tx.amount
        and tx.original_amount is None
    ):
        updates["original_amount"] = tx.amount


_DIFF_FIELDS = ("date", "amount", "category", "tags", "payer_percentage")


@define(slots=True)
class BulkUpdateTransactionsUseCase:
    async def execute(
        self,
        command: BulkUpdateTransactionsCommand,
        uow: UnitOfWorkProtocol,
    ) -> BulkUpdateTransactionsResult:
        if not command.transaction_ids:
            raise ValidationError("At least one transaction ID is required")

        updates = _collect_updates(command)
        if not updates:
            raise ValidationError("At least one field to update is required")

        # date/amount only allowed for single-item edits
        is_single = len(command.transaction_ids) == 1
        if not is_single and ("date" in updates or "amount" in updates):
            raise ValidationError(
                "date and amount can only be changed for a single transaction"
            )

        if (
            command.payer_percentage is not _UNSET
            and command.payer_percentage is not None
        ):
            if not isinstance(command.payer_percentage, int):
                raise ValidationError("payer_percentage must be an integer")
            validate_payer_percentage(command.payer_percentage)

        async with uow:
            transactions = await fetch_and_validate(uow, command.transaction_ids)

            # For date changes, also validate the target period
            if "date" in updates:
                tx = transactions[command.transaction_ids[0]]
                new_date = updates["date"]
                if new_date != tx.date and isinstance(new_date, date):
                    await assert_period_not_finalized(
                        uow, new_date.year, new_date.month
                    )

            all_edits: list[TransactionEdit] = []
            updated_transactions: list[Transaction] = []
            now = datetime.now(UTC)
            uses_immutable_fields = "date" in updates or "amount" in updates

            for tx_id in command.transaction_ids:
                tx = transactions[tx_id]
                tx_updates = dict(updates)
                _preserve_originals(tx_updates, tx)

                edits = [
                    e
                    for name in _DIFF_FIELDS
                    if name in tx_updates
                    and (
                        e := compute_edit(
                            tx, name, getattr(tx, name), tx_updates[name], now
                        )
                    )
                ]
                if not edits:
                    continue

                all_edits.extend(edits)
                updated_tx: Transaction = evolve(tx, **tx_updates)  # type: ignore[arg-type]
                updated_transactions.append(updated_tx)

                if uses_immutable_fields:
                    await uow.transactions.update_all_fields(updated_tx)
                else:
                    await uow.transactions.update_mutable_fields(updated_tx)

            if all_edits:
                await uow.transaction_edits.save_batch(all_edits)

            await uow.commit()
            return BulkUpdateTransactionsResult(
                updated_transactions=updated_transactions,
                edits=all_edits,
                updated_count=len(updated_transactions),
            )
