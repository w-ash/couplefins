from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.budget import BudgetOverview, compute_budget_overview
from src.domain.categories import (
    build_category_lookup,
    get_personal_included_categories,
)
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetBudgetOverviewCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)


@define(frozen=True, slots=True)
class GetBudgetOverviewResult:
    overview: BudgetOverview
    budgets: list[CategoryGroupBudget]


@define(slots=True)
class GetBudgetOverviewUseCase:
    async def execute(
        self, command: GetBudgetOverviewCommand, uow: UnitOfWorkProtocol
    ) -> GetBudgetOverviewResult:
        async with uow:
            budgets = await uow.category_group_budgets.get_all()
            categories = await uow.categories.get_all()
            category_groups = await uow.category_groups.get_all()

            personal_cats = get_personal_included_categories(categories)
            if personal_cats:
                year_txs = await uow.transactions.get_by_year(command.year)
            else:
                year_txs = await uow.transactions.get_household_by_year(command.year)

            category_lookup = build_category_lookup(categories, category_groups)

            overview = compute_budget_overview(
                budgets,
                year_txs,
                category_lookup,
                category_groups,
                command.year,
                command.month,
                personal_categories=personal_cats,
            )

            return GetBudgetOverviewResult(overview=overview, budgets=budgets)
