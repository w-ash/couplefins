from datetime import date
from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import positive_decimal
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SaveBudgetCommand:
    group_id: uuid.UUID
    monthly_amount: Decimal = field(validator=positive_decimal)
    effective_from: date
    person_id: uuid.UUID | None = None


@define(frozen=True, slots=True)
class SaveBudgetResult:
    budget: CategoryGroupBudget


@define(slots=True)
class SaveBudgetUseCase:
    async def execute(
        self, command: SaveBudgetCommand, uow: UnitOfWorkProtocol
    ) -> SaveBudgetResult:
        async with uow:
            await require_by_id(
                uow.category_groups.get_by_id, command.group_id, "Category group"
            )
            if command.person_id is not None:
                await require_by_id(uow.persons.get_by_id, command.person_id, "Person")

            budget = CategoryGroupBudget(
                id=uuid.uuid4(),
                group_id=command.group_id,
                monthly_amount=command.monthly_amount,
                effective_from=command.effective_from,
                person_id=command.person_id,
            )
            saved = await uow.category_group_budgets.save(budget)
            await uow.commit()
            return SaveBudgetResult(budget=saved)
