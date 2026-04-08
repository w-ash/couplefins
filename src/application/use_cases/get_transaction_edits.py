import asyncio
from uuid import UUID

from attrs import define

from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.import_event import ImportEvent
from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetTransactionEditsCommand:
    transaction_id: UUID


@define(frozen=True, slots=True)
class GetTransactionEditsResult:
    edits: list[TransactionEdit]
    import_event: ImportEvent | None


@define(slots=True)
class GetTransactionEditsUseCase:
    async def execute(
        self,
        command: GetTransactionEditsCommand,
        uow: UnitOfWorkProtocol,
    ) -> GetTransactionEditsResult:
        async with uow:
            tx = await require_by_id(
                uow.transactions.get_by_id, command.transaction_id, "Transaction"
            )
            edits, upload = await asyncio.gather(
                uow.transaction_edits.get_by_transaction_id(command.transaction_id),
                uow.uploads.get_by_id(tx.upload_id),
            )
            import_event = (
                ImportEvent(person_id=upload.person_id, imported_at=upload.uploaded_at)
                if upload is not None
                else None
            )
            return GetTransactionEditsResult(edits=edits, import_event=import_event)
