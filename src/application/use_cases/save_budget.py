from datetime import date
from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import positive_decimal
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.exceptions import NotFoundError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SaveBudgetCommand:
    group_id: uuid.UUID
    monthly_amount: Decimal = field(validator=positive_decimal)
    effective_from: date


@define(frozen=True, slots=True)
class SaveBudgetResult:
    budget: CategoryGroupBudget


@define(slots=True)
class SaveBudgetUseCase:
    async def execute(
        self, command: SaveBudgetCommand, uow: UnitOfWorkProtocol
    ) -> SaveBudgetResult:
        async with uow:
            group = await uow.category_groups.get_by_id(command.group_id)
            if group is None:
                raise NotFoundError(f"Category group {command.group_id} not found")

            budget = CategoryGroupBudget(
                id=uuid.uuid4(),
                group_id=command.group_id,
                monthly_amount=command.monthly_amount,
                effective_from=command.effective_from,
            )
            saved = await uow.category_group_budgets.save(budget)
            await uow.commit()
            return SaveBudgetResult(budget=saved)
