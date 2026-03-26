from collections import defaultdict
from collections.abc import Set
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from attrs import define, evolve

from src.domain.categories import (
    CategoryBreakdown,
    CategoryGroupBreakdown,
    compute_category_breakdowns,
    group_category_breakdowns,
)
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.transaction import Transaction
from src.domain.splits import compute_shares

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
    shared_spending: Decimal | None = None
    personal_spending: Decimal | None = None


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


def _is_budget_relevant(tx: Transaction, personal_categories: Set[str]) -> bool:
    if tx.is_excluded:
        return False
    return tx.household or tx.category in personal_categories


def compute_average_monthly_spending(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    through_month: int,
    personal_categories: Set[str] = frozenset(),
) -> dict[UUID, Decimal]:
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in year_txs:
        if _is_budget_relevant(tx, personal_categories) and tx.amount < 0:
            by_month[tx.date.month].append(tx)

    group_totals: dict[UUID, Decimal] = defaultdict(Decimal)
    months_with_data: set[int] = set()

    for month, txs in by_month.items():
        if month > through_month:
            continue
        months_with_data.add(month)
        breakdowns = compute_category_breakdowns(
            txs, category_lookup, personal_categories
        )
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


def _assemble_overview(
    statuses: list[CategoryGroupBudgetStatus],
    year: int,
    month: int,
) -> BudgetOverview:
    """Sort statuses (budgeted first) and assemble totals into BudgetOverview."""
    budgeted = [s for s in statuses if s.monthly_budget is not None]
    unbudgeted = [s for s in statuses if s.monthly_budget is None]

    budgeted.sort(
        key=lambda s: (s.monthly_spent - (s.monthly_budget or Decimal(0)),),
        reverse=True,
    )
    unbudgeted.sort(key=lambda s: s.monthly_spent, reverse=True)

    return BudgetOverview(
        year=year,
        month=month,
        group_statuses=[*budgeted, *unbudgeted],
        total_monthly_budget=sum(
            (s.monthly_budget for s in budgeted if s.monthly_budget),
            Decimal(0),
        ),
        total_monthly_spent=sum((s.monthly_spent for s in budgeted), Decimal(0)),
        total_ytd_budget=sum(
            (s.ytd_budget for s in budgeted if s.ytd_budget), Decimal(0)
        ),
        total_ytd_spent=sum((s.ytd_spent for s in budgeted), Decimal(0)),
    )


def compute_budget_overview(  # noqa: PLR0913, PLR0917
    budgets: list[CategoryGroupBudget],
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    groups: list[CategoryGroup],
    year: int,
    month: int,
    personal_categories: Set[str] = frozenset(),
) -> BudgetOverview:
    group_names = {g.id: g.name for g in groups}

    budgets_by_group: dict[UUID, list[CategoryGroupBudget]] = defaultdict(list)
    for b in budgets:
        budgets_by_group[b.group_id].append(b)

    ytd_txs = [
        tx
        for tx in year_txs
        if _is_budget_relevant(tx, personal_categories) and tx.date.month <= month
    ]
    month_txs = [tx for tx in ytd_txs if tx.date.month == month]

    month_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd
        for bd in compute_category_breakdowns(
            month_txs, category_lookup, personal_categories
        )
    }
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd
        for bd in compute_category_breakdowns(
            ytd_txs, category_lookup, personal_categories
        )
    }

    avg_spending = compute_average_monthly_spending(
        year_txs, category_lookup, month, personal_categories
    )

    statuses: list[CategoryGroupBudgetStatus] = []
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
        if status.monthly_budget is not None or status.monthly_spent > 0:
            statuses.append(status)

    return _assemble_overview(statuses, year, month)


def _compute_person_share(tx: Transaction, person_id: UUID) -> Decimal:
    """Compute what one person's share is for a transaction."""
    payer_share, other_share = compute_shares(tx.amount, tx.payer_percentage)
    return payer_share if tx.payer_person_id == person_id else other_share


def _is_personal_budget_relevant(tx: Transaction, person_id: UUID) -> bool:
    if tx.is_excluded or tx.is_settlement:
        return False
    return tx.household or tx.payer_person_id == person_id


def _compute_personal_breakdowns(
    txs: list[Transaction],
    person_id: UUID,
    category_lookup: dict[str, tuple[UUID, str]],
) -> tuple[list[CategoryGroupBreakdown], dict[UUID | None, tuple[Decimal, Decimal]]]:
    """Compute category breakdowns using person's share amounts.

    Returns (breakdowns, spending_split) where spending_split maps
    group_id → (shared_spending, personal_spending).
    """
    uncategorized = "Uncategorized"

    cat_total: dict[str, Decimal] = defaultdict(Decimal)
    cat_count: dict[str, int] = defaultdict(int)
    cat_household: dict[str, Decimal] = defaultdict(Decimal)
    cat_personal: dict[str, dict[UUID, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )
    group_shared: dict[UUID | None, Decimal] = defaultdict(Decimal)
    group_personal: dict[UUID | None, Decimal] = defaultdict(Decimal)

    for tx in txs:
        gid, _ = category_lookup.get(tx.category, (None, uncategorized))
        if tx.household:
            share = _compute_person_share(tx, person_id)
            cat_total[tx.category] += share
            cat_count[tx.category] += 1
            cat_household[tx.category] += share
            group_shared[gid] += share
        else:
            amount = abs(tx.amount)
            cat_total[tx.category] += amount
            cat_count[tx.category] += 1
            cat_personal[tx.category][person_id] += amount
            group_personal[gid] += amount

    category_breakdowns: list[CategoryBreakdown] = []
    for cat, amount in cat_total.items():
        gid, gname = category_lookup.get(cat, (None, uncategorized))
        category_breakdowns.append(
            CategoryBreakdown(
                category=cat,
                group_id=gid,
                group_name=gname,
                total_amount=amount,
                transaction_count=cat_count[cat],
                household_amount=cat_household.get(cat, Decimal(0)),
                personal_amounts=dict(cat_personal.get(cat, {})),
            )
        )

    all_gids = set(group_shared) | set(group_personal)
    spending_split = {
        gid: (group_shared.get(gid, Decimal(0)), group_personal.get(gid, Decimal(0)))
        for gid in all_gids
    }

    return group_category_breakdowns(category_breakdowns), spending_split


def compute_personal_budget_overview(  # noqa: PLR0913, PLR0914, PLR0917
    budgets: list[CategoryGroupBudget],
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    groups: list[CategoryGroup],
    year: int,
    month: int,
    person_id: UUID,
) -> BudgetOverview:
    """Compute budget overview from one person's perspective.

    Spending = person's share of household txs + their personal txs.
    """
    group_names = {g.id: g.name for g in groups}

    budgets_by_group: dict[UUID, list[CategoryGroupBudget]] = defaultdict(list)
    for b in budgets:
        budgets_by_group[b.group_id].append(b)

    ytd_txs = [
        tx
        for tx in year_txs
        if _is_personal_budget_relevant(tx, person_id) and tx.date.month <= month
    ]
    month_txs = [tx for tx in ytd_txs if tx.date.month == month]

    month_breakdowns, month_split = _compute_personal_breakdowns(
        month_txs, person_id, category_lookup
    )
    ytd_breakdowns, _ = _compute_personal_breakdowns(
        ytd_txs, person_id, category_lookup
    )

    month_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd for bd in month_breakdowns
    }
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd for bd in ytd_breakdowns
    }

    avg_txs = [
        tx
        for tx in year_txs
        if _is_personal_budget_relevant(tx, person_id) and tx.amount < 0
    ]
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in avg_txs:
        by_month[tx.date.month].append(tx)

    group_totals: dict[UUID, Decimal] = defaultdict(Decimal)
    months_with_data: set[int] = set()
    for m, txs in by_month.items():
        if m > month:
            continue
        months_with_data.add(m)
        bds, _ = _compute_personal_breakdowns(txs, person_id, category_lookup)
        for bd in bds:
            if bd.group_id is not None:
                group_totals[bd.group_id] += bd.total_amount

    num_months = len(months_with_data) or 1
    avg_spending = {gid: total / num_months for gid, total in group_totals.items()}

    statuses: list[CategoryGroupBudgetStatus] = []
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
        shared, personal = month_split.get(gid, (Decimal(0), Decimal(0)))
        status = evolve(status, shared_spending=shared, personal_spending=personal)
        if status.monthly_budget is not None or status.monthly_spent > 0:
            statuses.append(status)

    return _assemble_overview(statuses, year, month)
