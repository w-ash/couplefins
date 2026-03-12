from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.budget import BudgetOverview, compute_budget_overview
from src.domain.categories import build_category_lookup
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
            category_mappings = await uow.category_mappings.get_all()
            category_groups = await uow.category_groups.get_all()
            year_txs = await uow.transactions.get_shared_by_year(command.year)

            category_lookup = build_category_lookup(category_mappings, category_groups)

            overview = compute_budget_overview(
                budgets,
                year_txs,
                category_lookup,
                category_groups,
                command.year,
                command.month,
            )

            return GetBudgetOverviewResult(overview=overview, budgets=budgets)
