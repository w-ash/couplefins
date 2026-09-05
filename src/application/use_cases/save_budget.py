from decimal import Decimal
import uuid

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_decimal,
    positive_int,
)
from src.application.use_cases._shared.entity_lookup import require_by_id
from src.application.use_cases._shared.finalization import (
    assert_period_not_finalized,
)
from src.domain.entities.category_group import is_spending_kind
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class SaveBudgetCommand:
    group_id: uuid.UUID
    monthly_amount: Decimal = field(validator=positive_decimal)
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
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
            group = await require_by_id(
                uow.category_groups.get_by_id, command.group_id, "Category group"
            )
            if not is_spending_kind(group.kind):
                raise ValidationError("Only spending groups can carry a budget")
            if command.person_id is not None:
                await require_by_id(uow.persons.get_by_id, command.person_id, "Person")
            await assert_period_not_finalized(uow, command.year, command.month)

            existing = await uow.category_group_budgets.get_by_month(
                command.year, command.month, command.person_id
            )
            budget_id = (
                next((b.id for b in existing if b.group_id == command.group_id), None)
                or uuid.uuid4()
            )

            budget = CategoryGroupBudget(
                id=budget_id,
                group_id=command.group_id,
                monthly_amount=command.monthly_amount,
                year=command.year,
                month=command.month,
                person_id=command.person_id,
            )
            saved = await uow.category_group_budgets.save(budget)
            await uow.commit()
            return SaveBudgetResult(budget=saved)
