from uuid import UUID

from attrs import define

from src.application.use_cases._shared.budget_ownership import (
    require_budget_ownership,
)
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_period_not_finalized,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class DeleteBudgetCommand:
    budget_id: UUID
    person_id: UUID  # current user — for ownership check


@define(frozen=True, slots=True)
class DeleteBudgetResult:
    """Confirms deletion."""


@define(slots=True)
class DeleteBudgetUseCase:
    async def execute(
        self, command: DeleteBudgetCommand, uow: UnitOfWorkProtocol
    ) -> DeleteBudgetResult:
        async with uow:
            existing = await require_by_id(
                uow.category_group_budgets.get_by_id, command.budget_id, "Budget"
            )

            require_budget_ownership(existing, command.person_id)
            await assert_period_not_finalized(uow, existing.year, existing.month)

            await uow.category_group_budgets.delete(command.budget_id)
            await uow.commit()
            return DeleteBudgetResult()
