from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    PersonScope,
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
from src.domain.categories import build_category_lookup
from src.domain.entities.person import Person
from src.domain.insights import (
    CategoryComparison,
    GroupComparison,
    MonthlyGroupSpending,
    SpendingFlow,
    SpendingTrends,
    compute_category_comparisons,
    compute_comparison_cards,
    compute_spending_flow,
    compute_spending_trends,
)
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSpendingTrendsCommand:
    year: int | None = field(default=None, validator=optional_positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    comparison_year: int | None = field(default=None, validator=optional_positive_int)
    with_comparison: bool = True
    scope: PersonScope = "household"
    person_id: UUID | None = None

    def __attrs_post_init__(self) -> None:
        require_person_for_personal_scope(self.scope, self.person_id)


@define(frozen=True, slots=True)
class GetSpendingTrendsResult:
    year: int
    month: int
    trends: SpendingTrends
    comparison_cards: list[GroupComparison]
    category_comparisons: list[CategoryComparison]
    month_flow: SpendingFlow
    ytd_flow: SpendingFlow
    persons: list[Person]
    comparison_monthly_group_spending: list[MonthlyGroupSpending] = field(factory=list)


@define(slots=True)
class GetSpendingTrendsUseCase:
    async def execute(
        self, command: GetSpendingTrendsCommand, uow: UnitOfWorkProtocol
    ) -> GetSpendingTrendsResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            # Resolve before fetching: the row fetch needs the resolved year.
            year, target_month = await resolve_period(
                uow, ctx, command.year, command.month
            )
            # Year to date ends at the month being viewed, in every year —
            # the label says "Jan-Mar", and Budget and Dashboard bound their
            # YTD the same way. December gives the whole year.
            through_month = target_month
            year_txs = await fetch_year_spending_rows(uow, year, command.scope, ctx)
            category_lookup = build_category_lookup(ctx.categories, ctx.category_groups)

            trends = compute_spending_trends(
                year_txs,
                category_lookup,
                year,
                through_month=through_month,
                person_id=command.person_id,
            )

            comparison_cards = compute_comparison_cards(
                year_txs, category_lookup, target_month, person_id=command.person_id
            )
            category_comparisons = compute_category_comparisons(
                year_txs, category_lookup, target_month, person_id=command.person_id
            )

            # Both flows come from the rows already fetched; the YTD window
            # ends at `through_month`, so its cells sum to the YTD summaries.
            month_flow = compute_spending_flow(
                year_txs,
                category_lookup,
                person_id=command.person_id,
                months={target_month},
            )
            ytd_flow = compute_spending_flow(
                year_txs,
                category_lookup,
                person_id=command.person_id,
                months=range(1, through_month + 1),
            )

            # Every view compares against the year before the resolved one
            # unless the caller names a different one — the rule lives here
            # alone, so the chart's dotted series is always year - 1. A caller
            # that does not plot it (the chat tool) skips the second year.
            comparison: list[MonthlyGroupSpending] = []
            if command.with_comparison:
                comparison_year = command.comparison_year or year - 1
                comp_txs = await fetch_year_spending_rows(
                    uow, comparison_year, command.scope, ctx
                )
                comparison = compute_spending_trends(
                    comp_txs,
                    category_lookup,
                    comparison_year,
                    person_id=command.person_id,
                ).monthly_group_spending

            return GetSpendingTrendsResult(
                year=year,
                month=target_month,
                trends=trends,
                comparison_cards=comparison_cards,
                category_comparisons=category_comparisons,
                month_flow=month_flow,
                ytd_flow=ytd_flow,
                persons=ctx.persons,
                comparison_monthly_group_spending=comparison,
            )
