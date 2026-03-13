from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from attrs import define, evolve

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.finalization import assert_periods_not_finalized

if TYPE_CHECKING:
    from src.domain.entities.transaction import Transaction


@define(frozen=True, slots=True)
class SplitEntry:
    transaction_id: UUID
    payer_percentage: int


@define(frozen=True, slots=True)
class UpdateTransactionSplitsCommand:
    splits: list[SplitEntry]


@define(frozen=True, slots=True)
class UpdateTransactionSplitsResult:
    updated_count: int


@define(slots=True)
class UpdateTransactionSplitsUseCase:
    async def execute(
        self,
        command: UpdateTransactionSplitsCommand,
        uow: UnitOfWorkProtocol,
    ) -> UpdateTransactionSplitsResult:
        if not command.splits:
            raise ValidationError("At least one split entry is required")

        for entry in command.splits:
            if not (0 <= entry.payer_percentage <= SplitDefaults.MAX_PAYER_PERCENTAGE):
                raise ValidationError(
                    f"payer_percentage must be 0-{SplitDefaults.MAX_PAYER_PERCENTAGE}, "
                    f"got {entry.payer_percentage}"
                )

        async with uow:
            ids = [entry.transaction_id for entry in command.splits]
            found = await uow.transactions.get_by_ids(ids)
            transactions: dict[UUID, Transaction] = {tx.id: tx for tx in found}
            missing = set(ids) - transactions.keys()
            if missing:
                raise NotFoundError(f"Transaction {next(iter(missing))} not found")

            affected_periods = {
                (tx.date.year, tx.date.month) for tx in transactions.values()
            }
            await assert_periods_not_finalized(uow, affected_periods)

            edits: list[TransactionEdit] = []
            now = datetime.now(UTC)

            for entry in command.splits:
                tx = transactions[entry.transaction_id]
                if tx.payer_percentage != entry.payer_percentage:
                    edits.append(
                        TransactionEdit(
                            id=uuid4(),
                            transaction_id=tx.id,
                            field_name="payer_percentage",
                            old_value=str(tx.payer_percentage)
                            if tx.payer_percentage is not None
                            else "",
                            new_value=str(entry.payer_percentage),
                            edited_at=now,
                        )
                    )
                updated = evolve(tx, payer_percentage=entry.payer_percentage)
                await uow.transactions.update_mutable_fields(updated)

            if edits:
                await uow.transaction_edits.save_batch(edits)

            await uow.commit()
            return UpdateTransactionSplitsResult(updated_count=len(command.splits))
