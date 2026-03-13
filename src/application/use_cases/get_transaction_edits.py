from uuid import UUID

from attrs import define

from src.domain.entities.transaction_edit import TransactionEdit
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetTransactionEditsCommand:
    transaction_id: UUID


@define(frozen=True, slots=True)
class GetTransactionEditsResult:
    edits: list[TransactionEdit]


@define(slots=True)
class GetTransactionEditsUseCase:
    async def execute(
        self,
        command: GetTransactionEditsCommand,
        uow: UnitOfWorkProtocol,
    ) -> GetTransactionEditsResult:
        async with uow:
            tx = await uow.transactions.get_by_id(command.transaction_id)
            if tx is None:
                raise NotFoundError(f"Transaction {command.transaction_id} not found")
            edits = await uow.transaction_edits.get_by_transaction_id(
                command.transaction_id
            )
            return GetTransactionEditsResult(edits=edits)
