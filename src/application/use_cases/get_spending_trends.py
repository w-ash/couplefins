from datetime import UTC, datetime
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    PersonScope,
    optional_month_range,
    optional_positive_int,
    positive_int,
    require_person_for_personal_scope,
)
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_year_spending_rows,
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
    year: int = field(validator=positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    comparison_year: int | None = field(default=None, validator=optional_positive_int)
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


def _resolve_months(command: GetSpendingTrendsCommand) -> tuple[int, int]:
    """(target_month, through_month) — a completed past year spans all 12
    months; only the in-progress current year is bounded at the current month."""
    now = datetime.now(UTC)
    target_month = command.month or now.month
    through_month = target_month if command.year == now.year else 12
    return target_month, through_month


@define(slots=True)
class GetSpendingTrendsUseCase:
    async def execute(
        self, command: GetSpendingTrendsCommand, uow: UnitOfWorkProtocol
    ) -> GetSpendingTrendsResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            year_txs = await fetch_year_spending_rows(
                uow, command.year, command.scope, ctx
            )
            category_lookup = build_category_lookup(ctx.categories, ctx.category_groups)

            target_month, through_month = _resolve_months(command)

            trends = compute_spending_trends(
                year_txs,
                category_lookup,
                command.year,
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

            comparison_monthly_group_spending: list[MonthlyGroupSpending] = []
            if command.comparison_year is not None:
                comp_txs = await fetch_year_spending_rows(
                    uow, command.comparison_year, command.scope, ctx
                )
                comp_trends = compute_spending_trends(
                    comp_txs,
                    category_lookup,
                    command.comparison_year,
                    person_id=command.person_id,
                )
                comparison_monthly_group_spending = comp_trends.monthly_group_spending

            return GetSpendingTrendsResult(
                year=command.year,
                month=target_month,
                trends=trends,
                comparison_cards=comparison_cards,
                category_comparisons=category_comparisons,
                month_flow=month_flow,
                ytd_flow=ytd_flow,
                persons=ctx.persons,
                comparison_monthly_group_spending=comparison_monthly_group_spending,
            )
