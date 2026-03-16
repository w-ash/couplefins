from datetime import UTC, datetime
from uuid import UUID

from attrs import define, evolve

from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

from ._shared.transaction_pipeline import (
    compute_edit,
    fetch_and_validate,
    validate_payer_percentage,
)


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
            validate_payer_percentage(entry.payer_percentage)

        async with uow:
            ids = [entry.transaction_id for entry in command.splits]
            transactions = await fetch_and_validate(uow, ids)

            now = datetime.now(UTC)
            edits = [
                edit
                for entry in command.splits
                if (
                    edit := compute_edit(
                        transactions[entry.transaction_id],
                        "payer_percentage",
                        transactions[entry.transaction_id].payer_percentage,
                        entry.payer_percentage,
                        now,
                    )
                )
            ]

            for entry in command.splits:
                tx = transactions[entry.transaction_id]
                if tx.payer_percentage == entry.payer_percentage:
                    continue
                updated = evolve(tx, payer_percentage=entry.payer_percentage)
                await uow.transactions.update_mutable_fields(updated)

            if edits:
                await uow.transaction_edits.save_batch(edits)

            await uow.commit()
            return UpdateTransactionSplitsResult(updated_count=len(edits))
