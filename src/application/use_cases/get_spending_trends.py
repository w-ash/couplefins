from collections import defaultdict
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
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.reconciliation_helpers import (
    reconcile_all_months,
)
from src.domain.budget import resolve_effective_budget
from src.domain.categories import build_category_lookup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
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
    budget_lines: dict[UUID, Decimal]
    settlement_trend: list[MonthlySettlement]
    monthly_person_paid: list[MonthlyPersonPaid]
    persons: list[Person]
    comparison_monthly_group_spending: list[MonthlyGroupSpending] = field(factory=list)


def _build_budget_lines(
    budgets: list[CategoryGroupBudget],
    target_date: date,
) -> dict[UUID, Decimal]:
    budgets_by_group: dict[UUID, list[CategoryGroupBudget]] = defaultdict(list)
    for b in budgets:
        budgets_by_group[b.group_id].append(b)

    result: dict[UUID, Decimal] = {}
    for group_id, group_budgets in budgets_by_group.items():
        effective = resolve_effective_budget(group_budgets, target_date)
        if effective:
            result[group_id] = effective.monthly_amount
    return result


def _build_settlement_trend(
    year_txs: list[Transaction],
    ctx: ReconciliationContext,
    year: int,
    settlements: list[Settlement],
) -> list[MonthlySettlement]:
    by_month = partition_by_month(year_txs, lambda tx: tx.date.month)
    month_summaries = reconcile_all_months(by_month, ctx, year)
    settlements_by_month = partition_by_month(settlements, lambda s: s.month)

    trend: list[MonthlySettlement] = []
    for month_num in sorted(month_summaries):
        summary = month_summaries[month_num]
        if summary.settlement is None:
            continue
        month_settlements = settlements_by_month.get(month_num, [])
        total_settled = sum((s.amount for s in month_settlements), Decimal(0))
        trend.append(
            MonthlySettlement(
                year=year,
                month=month_num,
                amount=summary.settlement.amount,
                from_person_id=summary.settlement.from_person_id,
                to_person_id=summary.settlement.to_person_id,
                is_settled=total_settled >= summary.settlement.amount,
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
            trends = compute_spending_trends(year_txs, category_lookup, command.year)

            target_month = command.month or datetime.now(UTC).month

            comparison_cards = compute_comparison_cards(
                year_txs, category_lookup, target_month
            )

            all_budgets = await uow.category_group_budgets.get_all()
            budget_lines = _build_budget_lines(
                all_budgets, date(command.year, target_month, 1)
            )

            all_year_settlements = await uow.settlements.get_by_year(command.year)
            settlement_trend = _build_settlement_trend(
                year_txs, ctx, command.year, all_year_settlements
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
