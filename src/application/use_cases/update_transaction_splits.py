from datetime import UTC, datetime
from uuid import UUID

from attrs import define, evolve

from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.split_rules import check_payer_percentage

from ._shared.command_validators import as_validation_error
from ._shared.transaction_pipeline import (
    NO_PAYER_SPLIT,
    compute_edit,
    fetch_and_validate,
    reject_joint_rows,
)


@define(frozen=True, slots=True)
class SplitEntry:
    transaction_id: UUID
    payer_percentage: int


@define(frozen=True, slots=True)
class UpdateTransactionSplitsCommand:
    splits: list[SplitEntry]
    edited_by_person_id: UUID | None = None


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
            as_validation_error(check_payer_percentage, entry.payer_percentage)

        async with uow:
            ids = [entry.transaction_id for entry in command.splits]
            transactions = await fetch_and_validate(uow, ids)
            reject_joint_rows(transactions.values(), NO_PAYER_SPLIT)

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
                        now=now,
                        edited_by_person_id=command.edited_by_person_id,
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
