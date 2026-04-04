from typing import Literal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.budget import (
    BudgetOverview,
    compute_budget_overview,
    compute_personal_budget_overview,
)
from src.domain.categories import (
    build_category_lookup,
    get_personal_included_categories,
)
from src.domain.entities.category import Category
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.exceptions import ValidationError
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetBudgetOverviewCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    scope: Literal["household", "personal"] = "household"
    person_id: UUID | None = None

    def __attrs_post_init__(self) -> None:
        if self.scope == "personal" and self.person_id is None:
            raise ValidationError("person_id is required for personal scope")


@define(frozen=True, slots=True)
class GetBudgetOverviewResult:
    overview: BudgetOverview
    budgets: list[CategoryGroupBudget]
    categories: list[Category]
    persons: list[Person]


@define(slots=True)
class GetBudgetOverviewUseCase:
    async def execute(
        self, command: GetBudgetOverviewCommand, uow: UnitOfWorkProtocol
    ) -> GetBudgetOverviewResult:
        async with uow:
            categories = await uow.categories.get_all()
            category_groups = await uow.category_groups.get_all()
            persons = await uow.persons.get_all()
            category_lookup = build_category_lookup(categories, category_groups)

            if command.scope == "personal" and command.person_id is not None:
                year_budgets = await uow.category_group_budgets.get_by_year(
                    command.year, command.person_id
                )
                month_budgets = [b for b in year_budgets if b.month == command.month]
                year_txs = await uow.transactions.get_by_year(command.year)
                overview = compute_personal_budget_overview(
                    month_budgets,
                    year_budgets,
                    year_txs,
                    category_lookup,
                    category_groups,
                    command.year,
                    command.month,
                    command.person_id,
                )
                budgets = month_budgets
            else:
                year_budgets = await uow.category_group_budgets.get_by_year(
                    command.year, None
                )
                month_budgets = [b for b in year_budgets if b.month == command.month]
                personal_cats = get_personal_included_categories(categories)
                if personal_cats:
                    year_txs = await uow.transactions.get_by_year(command.year)
                else:
                    year_txs = await uow.transactions.get_household_by_year(
                        command.year
                    )
                overview = compute_budget_overview(
                    month_budgets,
                    year_budgets,
                    year_txs,
                    category_lookup,
                    category_groups,
                    command.year,
                    command.month,
                    personal_categories=personal_cats,
                )
                budgets = month_budgets

            return GetBudgetOverviewResult(
                overview=overview,
                budgets=budgets,
                categories=categories,
                persons=persons,
            )
