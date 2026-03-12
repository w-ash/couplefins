from decimal import Decimal
from uuid import UUID

import attrs
from attrs import define, field

from src.application.use_cases._shared.command_validators import positive_decimal
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class UpdateBudgetCommand:
    budget_id: UUID
    monthly_amount: Decimal = field(validator=positive_decimal)


@define(frozen=True, slots=True)
class UpdateBudgetResult:
    budget: CategoryGroupBudget


@define(slots=True)
class UpdateBudgetUseCase:
    async def execute(
        self, command: UpdateBudgetCommand, uow: UnitOfWorkProtocol
    ) -> UpdateBudgetResult:
        async with uow:
            existing = await uow.category_group_budgets.get_by_id(command.budget_id)
            if existing is None:
                raise NotFoundError(f"Budget {command.budget_id} not found")

            updated = attrs.evolve(existing, monthly_amount=command.monthly_amount)
            saved = await uow.category_group_budgets.save(updated)
            await uow.commit()
            return UpdateBudgetResult(budget=saved)
