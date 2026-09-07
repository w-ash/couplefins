from typing import NamedTuple
from uuid import UUID

from attrs import Factory, define, field
from structlog.stdlib import get_logger

from src.application.use_cases._shared.command_validators import (
    PersonScope,
    Scope,
    optional_month_range,
    optional_positive_int,
    require_person_for_personal_scope,
)
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_year_spending_rows,
    resolve_period,
)
from src.domain.budget import (
    BudgetOverview,
    BudgetOverviewInputs,
    compute_budget_overview,
    find_copyable_source,
    has_budgets_for_month,
)
from src.domain.categories import (
    build_category_lookup,
    get_personal_included_categories,
)
from src.domain.entities.category import Category
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.spending_lens import HouseholdLens, PersonalLens, SpendingLens

logger = get_logger()


@define(frozen=True, slots=True)
class GetBudgetOverviewCommand:
    year: int | None = field(default=None, validator=optional_positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    scope: PersonScope = "household"
    person_id: UUID | None = None

    def __attrs_post_init__(self) -> None:
        require_person_for_personal_scope(self.scope, self.person_id)


@define(frozen=True, slots=True)
class GetBudgetOverviewResult:
    overview: BudgetOverview
    budgets: list[CategoryGroupBudget]
    categories: list[Category]
    persons: list[Person]
    copyable_source: tuple[int, int] | None = None
    next_month_has_budgets: bool = False
    source_budgets: list[CategoryGroupBudget] = Factory(list[CategoryGroupBudget])


_DECEMBER = 12


class _CopyIndicators(NamedTuple):
    copyable_source: tuple[int, int] | None
    next_month_has_budgets: bool
    source_budgets: list[CategoryGroupBudget]


def _compute_copy_indicators(
    all_budgets: list[CategoryGroupBudget],
    year: int,
    month: int,
    person_id: UUID | None,
) -> _CopyIndicators:
    scoped = [b for b in all_budgets if b.person_id is None or b.person_id == person_id]
    copyable = find_copyable_source(scoped, year, month)
    next_year, next_month = (year + 1, 1) if month == _DECEMBER else (year, month + 1)
    next_has = has_budgets_for_month(scoped, next_year, next_month)
    src = (
        [b for b in scoped if b.year == copyable[0] and b.month == copyable[1]]
        if copyable
        else []
    )
    return _CopyIndicators(copyable, next_has, src)


@define(slots=True)
class GetBudgetOverviewUseCase:
    async def execute(
        self, command: GetBudgetOverviewCommand, uow: UnitOfWorkProtocol
    ) -> GetBudgetOverviewResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            year, month = await resolve_period(uow, ctx, command.year, command.month)
            category_lookup = build_category_lookup(ctx.categories, ctx.category_groups)

            if command.scope == "personal" and command.person_id is not None:
                lens: SpendingLens = PersonalLens(command.person_id)
                fetch_scope: Scope = "personal"
                budget_owner: UUID | None = command.person_id
            else:
                personal_cats = get_personal_included_categories(ctx.categories)
                lens = HouseholdLens(personal_cats)
                fetch_scope = "all" if personal_cats else "household"
                budget_owner = None

            year_budgets = await uow.category_group_budgets.get_by_year(
                year, budget_owner
            )
            month_budgets = [b for b in year_budgets if b.month == month]
            year_txs = await fetch_year_spending_rows(uow, year, fetch_scope, ctx)
            overview = compute_budget_overview(
                BudgetOverviewInputs(
                    month_budgets,
                    year_budgets,
                    year_txs,
                    category_lookup,
                    ctx.category_groups,
                    year,
                    month,
                ),
                lens,
            )
            budgets = month_budgets

            if overview.spending_drift is not None:
                logger.warning(
                    "budget_spending_drift",
                    drift=str(overview.spending_drift),
                    year=year,
                    month=month,
                    scope=command.scope,
                )

            all_budgets = await uow.category_group_budgets.get_all()
            ci = _compute_copy_indicators(all_budgets, year, month, command.person_id)

            return GetBudgetOverviewResult(
                overview=overview,
                budgets=budgets,
                categories=ctx.categories,
                persons=ctx.persons,
                copyable_source=ci.copyable_source,
                next_month_has_budgets=ci.next_month_has_budgets,
                source_budgets=ci.source_budgets,
            )
