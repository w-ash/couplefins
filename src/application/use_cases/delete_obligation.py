from uuid import UUID

from attrs import define

from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteObligationCommand:
    obligation_id: UUID


@define(frozen=True, slots=True)
class DeleteObligationResult:
    deleted: bool


@define(slots=True)
class DeleteObligationUseCase:
    async def execute(
        self, command: DeleteObligationCommand, uow: UnitOfWorkProtocol
    ) -> DeleteObligationResult:
        """Delete an obligation. The row that paid it stays. Raise
        NotFoundError when it does not exist."""
        async with uow:
            if not await uow.obligations.delete(command.obligation_id):
                raise NotFoundError(f"Obligation {command.obligation_id} not found")
            await uow.commit()
            return DeleteObligationResult(deleted=True)
