from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_periods_not_finalized,
    months_of,
)
from src.application.use_cases._shared.transactions import (
    delete_transactions_with_links,
)
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteManualTransactionCommand:
    transaction_id: UUID


@define(frozen=True, slots=True)
class DeleteManualTransactionResult:
    deleted: bool


@define(slots=True)
class DeleteManualTransactionUseCase:
    async def execute(
        self, command: DeleteManualTransactionCommand, uow: UnitOfWorkProtocol
    ) -> DeleteManualTransactionResult:
        """Delete a hand-entered row with its edits and settlement links.

        Raise NotFoundError when the row does not exist, ValidationError
        when an import brought it in (a re-import owns those), and
        PeriodFinalizedError when its month is finalized.
        """
        async with uow:
            tx = await require_by_id(
                uow.transactions.get_by_id, command.transaction_id, "Transaction"
            )
            upload = await uow.uploads.get_by_id(tx.upload_id)
            if upload is None or not upload.is_manual:
                raise ValidationError(
                    "Only a hand-entered row can be deleted here; "
                    "an imported row changes with its import"
                )
            await assert_periods_not_finalized(uow, months_of([tx]))
            await delete_transactions_with_links(uow, [tx])
            await uow.commit()
            return DeleteManualTransactionResult(deleted=True)
