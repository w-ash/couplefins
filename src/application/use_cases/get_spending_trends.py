from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    optional_month_range,
    optional_positive_int,
    positive_int,
)
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.application.use_cases._shared.settlement_math import load_ledger
from src.domain.categories import build_category_lookup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.person import Person
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
from src.domain.ledger import MonthSettlementStatus, SettlementLedger
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


def _build_settlement_trend(
    ledger: SettlementLedger, year: int
) -> list[MonthlySettlement]:
    # Ledger months cover settlement-relevant rows (payer_percentage < 100,
    # household or not) — matching Dashboard/Settle Up — so a month whose only
    # settlement signal is a spotted / personal-split row is not dropped.
    return [
        MonthlySettlement(
            year=year,
            month=row.month,
            amount=row.gross.amount,
            from_person_id=row.gross.from_person_id,
            to_person_id=row.gross.to_person_id,
            # Ledger-derived — subsumes the old overpaid special case: an
            # overpaid month has zero remaining, so it reads as settled.
            is_settled=row.status is MonthSettlementStatus.SETTLED,
            status=row.status,
        )
        for row in ledger.months
        if row.year == year and row.gross is not None
    ]


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

            ledger = (await load_ledger(uow, ctx)).ledger
            settlement_trend = _build_settlement_trend(ledger, command.year)

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
