from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from attrs import define

from src.domain.categories import (
    CategoryBreakdown,
    CategoryGroupBreakdown,
    compute_category_breakdowns,
)
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.transaction import Transaction

HealthStatus = Literal["on_track", "near_limit", "over_budget"]

_NEAR_LIMIT_THRESHOLD = Decimal("0.80")


@define(frozen=True, slots=True)
class CategoryGroupBudgetStatus:
    group_id: UUID
    group_name: str
    budget_id: UUID | None
    monthly_budget: Decimal | None
    monthly_spent: Decimal
    ytd_budget: Decimal | None
    ytd_spent: Decimal
    monthly_health: HealthStatus | None
    ytd_health: HealthStatus | None
    average_monthly_spending: Decimal
    categories: list[CategoryBreakdown]


@define(frozen=True, slots=True)
class BudgetOverview:
    year: int
    month: int
    group_statuses: list[CategoryGroupBudgetStatus]
    total_monthly_budget: Decimal
    total_monthly_spent: Decimal
    total_ytd_budget: Decimal
    total_ytd_spent: Decimal


def resolve_effective_budget(
    budgets: list[CategoryGroupBudget],
    target_date: date,
) -> CategoryGroupBudget | None:
    applicable = [b for b in budgets if b.effective_from <= target_date]
    if not applicable:
        return None
    return max(applicable, key=lambda b: b.effective_from)


def compute_ytd_budget(
    budgets: list[CategoryGroupBudget],
    year: int,
    through_month: int,
) -> Decimal:
    total = Decimal(0)
    for month in range(1, through_month + 1):
        target = date(year, month, 1)
        effective = resolve_effective_budget(budgets, target)
        if effective:
            total += effective.monthly_amount
    return total


def determine_health(spent: Decimal, budget: Decimal) -> HealthStatus:
    if budget <= 0:
        return "over_budget" if spent > 0 else "on_track"
    ratio = spent / budget
    if ratio >= 1:
        return "over_budget"
    if ratio >= _NEAR_LIMIT_THRESHOLD:
        return "near_limit"
    return "on_track"


def compute_average_monthly_spending(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    through_month: int,
) -> dict[UUID, Decimal]:
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in year_txs:
        if tx.is_shared and tx.amount < 0:
            by_month[tx.date.month].append(tx)

    group_totals: dict[UUID, Decimal] = defaultdict(Decimal)
    months_with_data: set[int] = set()

    for month, txs in by_month.items():
        if month > through_month:
            continue
        months_with_data.add(month)
        breakdowns = compute_category_breakdowns(txs, category_lookup)
        for bd in breakdowns:
            if bd.group_id is not None:
                group_totals[bd.group_id] += bd.total_amount

    num_months = len(months_with_data) or 1
    return {gid: total / num_months for gid, total in group_totals.items()}


def _build_group_status(  # noqa: PLR0913, PLR0917
    gid: UUID,
    name: str,
    group_budgets: list[CategoryGroupBudget],
    month_by_group: dict[UUID | None, CategoryGroupBreakdown],
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown],
    avg_spending: dict[UUID, Decimal],
    year: int,
    month: int,
) -> CategoryGroupBudgetStatus:
    target_date = date(year, month, 1)
    effective = resolve_effective_budget(group_budgets, target_date)

    monthly_bd = month_by_group.get(gid)
    ytd_bd = ytd_by_group.get(gid)
    monthly_spent = monthly_bd.total_amount if monthly_bd else Decimal(0)
    ytd_spent = ytd_bd.total_amount if ytd_bd else Decimal(0)

    monthly_budget = effective.monthly_amount if effective else None
    ytd_budget_val = (
        compute_ytd_budget(group_budgets, year, month) if group_budgets else None
    )

    return CategoryGroupBudgetStatus(
        group_id=gid,
        group_name=name,
        budget_id=effective.id if effective else None,
        monthly_budget=monthly_budget,
        monthly_spent=monthly_spent,
        ytd_budget=ytd_budget_val if group_budgets else None,
        ytd_spent=ytd_spent,
        monthly_health=determine_health(monthly_spent, monthly_budget)
        if monthly_budget is not None
        else None,
        ytd_health=determine_health(ytd_spent, ytd_budget_val)
        if ytd_budget_val is not None
        else None,
        average_monthly_spending=avg_spending.get(gid, Decimal(0)),
        categories=monthly_bd.categories if monthly_bd else [],
    )


def compute_budget_overview(  # noqa: PLR0913, PLR0917
    budgets: list[CategoryGroupBudget],
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    groups: list[CategoryGroup],
    year: int,
    month: int,
) -> BudgetOverview:
    group_names = {g.id: g.name for g in groups}

    budgets_by_group: dict[UUID, list[CategoryGroupBudget]] = defaultdict(list)
    for b in budgets:
        budgets_by_group[b.group_id].append(b)

    month_txs = [tx for tx in year_txs if tx.is_shared and tx.date.month == month]
    ytd_txs = [tx for tx in year_txs if tx.is_shared and tx.date.month <= month]

    month_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd
        for bd in compute_category_breakdowns(month_txs, category_lookup)
    }
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd for bd in compute_category_breakdowns(ytd_txs, category_lookup)
    }

    avg_spending = compute_average_monthly_spending(year_txs, category_lookup, month)

    budgeted_statuses: list[CategoryGroupBudgetStatus] = []
    unbudgeted_statuses: list[CategoryGroupBudgetStatus] = []

    for gid, name in group_names.items():
        status = _build_group_status(
            gid,
            name,
            budgets_by_group.get(gid, []),
            month_by_group,
            ytd_by_group,
            avg_spending,
            year,
            month,
        )

        if status.monthly_budget is not None:
            budgeted_statuses.append(status)
        elif status.monthly_spent > 0:
            unbudgeted_statuses.append(status)

    budgeted_statuses.sort(
        key=lambda s: (s.monthly_spent - (s.monthly_budget or Decimal(0)),),
        reverse=True,
    )
    unbudgeted_statuses.sort(key=lambda s: s.monthly_spent, reverse=True)

    return BudgetOverview(
        year=year,
        month=month,
        group_statuses=[*budgeted_statuses, *unbudgeted_statuses],
        total_monthly_budget=sum(
            (s.monthly_budget for s in budgeted_statuses if s.monthly_budget),
            Decimal(0),
        ),
        total_monthly_spent=sum(
            (s.monthly_spent for s in budgeted_statuses), Decimal(0)
        ),
        total_ytd_budget=sum(
            (s.ytd_budget for s in budgeted_statuses if s.ytd_budget), Decimal(0)
        ),
        total_ytd_spent=sum((s.ytd_spent for s in budgeted_statuses), Decimal(0)),
    )
