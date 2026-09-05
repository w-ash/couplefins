from datetime import UTC, datetime
from decimal import Decimal
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
from src.application.use_cases._shared.settlement_math import load_ledger
from src.application.use_cases._shared.transaction_reads import (
    fetch_year_spending_rows,
)
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
            amount=row.charged.amount,
            from_person_id=row.charged.from_person_id,
            to_person_id=row.charged.to_person_id,
            is_settled=row.status is MonthSettlementStatus.SETTLED,
            status=row.status,
        )
        for row in ledger.months
        if row.year == year and row.charged is not None
    ]


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

            # Household budgets (person_id=None) or the person's own budgets.
            year_budgets = await uow.category_group_budgets.get_by_year(
                command.year, command.person_id
            )
            budget_lines = _build_budget_lines(year_budgets)

            # "Who's paying" (who fronted the household money, settlement
            # trend) is a couple-level fact with no personal reading; the
            # personal page hides it, so skip the all-time ledger work.
            settlement_trend: list[MonthlySettlement] = []
            monthly_person_paid: list[MonthlyPersonPaid] = []
            if command.scope == "household":
                ledger = (await load_ledger(uow, ctx)).ledger
                settlement_trend = _build_settlement_trend(ledger, command.year)
                monthly_person_paid = compute_person_paid_by_month(
                    year_txs, category_lookup
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
                budget_lines=budget_lines,
                settlement_trend=settlement_trend,
                monthly_person_paid=monthly_person_paid,
                persons=ctx.persons,
                comparison_monthly_group_spending=comparison_monthly_group_spending,
            )
