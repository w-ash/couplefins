from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    optional_month_range,
    optional_positive_int,
    positive_int,
)
from src.application.use_cases._shared.date_math import partition_by_month
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.domain.categories import build_category_lookup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.entities.settlement import Settlement
from src.domain.insights import (
    GroupComparison,
    MonthlyGroupSpending,
    MonthlyPersonPaid,
    MonthlySettlement,
    SpendingTrends,
    compute_comparison_cards,
    compute_person_paid_by_month,
    compute_spending_trends,
)
from src.domain.reconciliation import compute_gross_settlement, compute_net_position
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSpendingTrendsCommand:
    year: int = field(validator=positive_int)
    month: int | None = field(default=None, validator=optional_month_range)
    comparison_year: int | None = field(default=None, validator=optional_positive_int)


@define(frozen=True, slots=True)
class GetSpendingTrendsResult:
    year: int
    month: int
    trends: SpendingTrends
    comparison_cards: list[GroupComparison]
    budget_lines: dict[UUID, dict[int, Decimal]]
    settlement_trend: list[MonthlySettlement]
    monthly_person_paid: list[MonthlyPersonPaid]
    persons: list[Person]
    comparison_monthly_group_spending: list[MonthlyGroupSpending] = field(factory=list)


def _build_budget_lines(
    budgets: list[CategoryGroupBudget],
) -> dict[UUID, dict[int, Decimal]]:
    result: dict[UUID, dict[int, Decimal]] = {}
    for b in budgets:
        result.setdefault(b.group_id, {})[b.month] = b.monthly_amount
    return result


def _resolve_months(command: GetSpendingTrendsCommand) -> tuple[int, int]:
    """(target_month, through_month) — a completed past year spans all 12
    months; only the in-progress current year is bounded at the current month."""
    now = datetime.now(UTC)
    target_month = command.month or now.month
    through_month = target_month if command.year == now.year else 12
    return target_month, through_month


async def _build_settlement_trend(
    uow: UnitOfWorkProtocol,
    person_ids: list[UUID],
    year: int,
    settlements: list[Settlement],
) -> list[MonthlySettlement]:
    # Gross is computed over settlement-relevant rows (payer_percentage < 100,
    # household or not) — matching Dashboard/Settle Up — so a month whose only
    # settlement signal is a spotted / personal-split row is not dropped.
    settlement_txs = await uow.transactions.get_settlement_relevant_by_date_range(
        date(year, 1, 1), date(year, 12, 31)
    )
    by_month = partition_by_month(settlement_txs, lambda tx: tx.date.month)
    # get_by_year only returns annotated rows; `or 0` is typing-only
    # narrowing (month is never 0).
    settlements_by_month = partition_by_month(settlements, lambda s: s.month or 0)

    trend: list[MonthlySettlement] = []
    for month_num in sorted(by_month):
        gross = compute_gross_settlement(by_month[month_num], person_ids)
        if gross is None:
            continue
        month_settlements = settlements_by_month.get(month_num, [])
        net = compute_net_position(gross, month_settlements)
        # An overpayment leaves a non-zero net whose direction is *reversed*
        # from the gross — the debt was still covered, so the month is settled.
        overpaid = net is not None and net.from_person_id != gross.from_person_id
        trend.append(
            MonthlySettlement(
                year=year,
                month=month_num,
                amount=gross.amount,
                from_person_id=gross.from_person_id,
                to_person_id=gross.to_person_id,
                is_settled=net is None or net.amount == Decimal(0) or overpaid,
            )
        )
    return trend


@define(slots=True)
class GetSpendingTrendsUseCase:
    async def execute(
        self, command: GetSpendingTrendsCommand, uow: UnitOfWorkProtocol
    ) -> GetSpendingTrendsResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            year_txs = await uow.transactions.get_household_by_year(command.year)
            category_lookup = build_category_lookup(ctx.categories, ctx.category_groups)

            target_month, through_month = _resolve_months(command)

            trends = compute_spending_trends(
                year_txs, category_lookup, command.year, through_month=through_month
            )

            comparison_cards = compute_comparison_cards(
                year_txs, category_lookup, target_month
            )

            year_budgets = await uow.category_group_budgets.get_by_year(
                command.year, None
            )
            budget_lines = _build_budget_lines(year_budgets)

            all_year_settlements = await uow.settlements.get_by_year(command.year)
            settlement_trend = await _build_settlement_trend(
                uow, ctx.person_ids, command.year, all_year_settlements
            )

            monthly_person_paid = compute_person_paid_by_month(
                year_txs, category_lookup
            )

            comparison_monthly_group_spending: list[MonthlyGroupSpending] = []
            if command.comparison_year is not None:
                comp_txs = await uow.transactions.get_household_by_year(
                    command.comparison_year
                )
                comp_trends = compute_spending_trends(
                    comp_txs, category_lookup, command.comparison_year
                )
                comparison_monthly_group_spending = comp_trends.monthly_group_spending

            return GetSpendingTrendsResult(
                year=command.year,
                month=target_month,
                trends=trends,
                comparison_cards=comparison_cards,
                budget_lines=budget_lines,
                settlement_trend=settlement_trend,
                monthly_person_paid=monthly_person_paid,
                persons=ctx.persons,
                comparison_monthly_group_spending=comparison_monthly_group_spending,
            )
