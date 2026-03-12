from uuid import UUID

from attrs import define

from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteBudgetCommand:
    budget_id: UUID


@define(frozen=True, slots=True)
class DeleteBudgetResult:
    """Confirms deletion."""


@define(slots=True)
class DeleteBudgetUseCase:
    async def execute(
        self, command: DeleteBudgetCommand, uow: UnitOfWorkProtocol
    ) -> DeleteBudgetResult:
        async with uow:
            existing = await uow.category_group_budgets.get_by_id(command.budget_id)
            if existing is None:
                raise NotFoundError(f"Budget {command.budget_id} not found")

            await uow.category_group_budgets.delete(command.budget_id)
            await uow.commit()
            return DeleteBudgetResult()
