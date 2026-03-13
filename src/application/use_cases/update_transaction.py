from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from attrs import define, evolve, field

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.finalization import assert_period_not_finalized

if TYPE_CHECKING:
    from src.domain.entities.transaction import Transaction

_SENTINEL = object()


@define(frozen=True, slots=True)
class UpdateTransactionCommand:
    transaction_id: UUID
    date: date | None = None
    amount: Decimal | None = None
    category: str | None = None
    tags: tuple[str, ...] | None = None
    payer_percentage: int | object = field(default=_SENTINEL)


@define(frozen=True, slots=True)
class UpdateTransactionResult:
    transaction: Transaction
    edits: list[TransactionEdit]


def _field_str(value: date | Decimal | str | int | tuple[str, ...] | None) -> str:
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else str(value)


type _FieldValue = date | Decimal | str | int | tuple[str, ...] | None


def _collect_updates(
    command: UpdateTransactionCommand,
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
    if command.payer_percentage is not _SENTINEL:
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


def _compute_edits(
    updates: dict[str, _FieldValue], tx: Transaction
) -> list[TransactionEdit]:
    now = datetime.now(UTC)
    return [
        TransactionEdit(
            id=uuid4(),
            transaction_id=tx.id,
            field_name=name,
            old_value=_field_str(getattr(tx, name)),
            new_value=_field_str(updates[name]),
            edited_at=now,
        )
        for name in _DIFF_FIELDS
        if name in updates and getattr(tx, name) != updates[name]
    ]


@define(slots=True)
class UpdateTransactionUseCase:
    async def execute(
        self,
        command: UpdateTransactionCommand,
        uow: UnitOfWorkProtocol,
    ) -> UpdateTransactionResult:
        if (
            command.payer_percentage is not _SENTINEL
            and command.payer_percentage is not None
        ):
            pct = command.payer_percentage
            if not isinstance(pct, int) or not (
                0 <= pct <= SplitDefaults.MAX_PAYER_PERCENTAGE
            ):
                raise ValidationError(
                    f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, "
                    f"got {pct}"
                )

        async with uow:
            tx = await uow.transactions.get_by_id(command.transaction_id)
            if tx is None:
                raise NotFoundError(f"Transaction {command.transaction_id} not found")

            await assert_period_not_finalized(uow, tx.date.year, tx.date.month)

            if command.date is not None and command.date != tx.date:
                await assert_period_not_finalized(
                    uow, command.date.year, command.date.month
                )

            updates = _collect_updates(command)
            _preserve_originals(updates, tx)
            edits = _compute_edits(updates, tx)

            if not edits:
                return UpdateTransactionResult(transaction=tx, edits=[])

            updated_tx: Transaction = evolve(tx, **updates)  # type: ignore[arg-type]
            await uow.transaction_edits.save_batch(edits)
            await uow.transactions.update_all_fields(updated_tx)
            await uow.commit()

            return UpdateTransactionResult(transaction=updated_tx, edits=edits)
