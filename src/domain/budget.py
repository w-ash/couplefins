from collections import defaultdict
from decimal import Decimal
from typing import Literal
from uuid import UUID

from attrs import Factory, define

from src.domain.categories import CategoryBreakdown, CategoryGroupBreakdown
from src.domain.constants import UNCATEGORIZED_GROUP_NAME
from src.domain.entities.category_group import CategoryGroup, is_spending_kind
from src.domain.entities.category_group_budget import CategoryGroupBudget
from src.domain.entities.transaction import Transaction
from src.domain.spending_lens import (
    HouseholdLens,
    SpendingLens,
    compute_breakdowns,
    select,
    source_split,
)

HealthStatus = Literal["on_track", "near_limit", "over_budget"]

# The default lens: the household's own spending, no include_personal opt-ins.
HOUSEHOLD_LENS = HouseholdLens()

_NEAR_LIMIT_THRESHOLD = Decimal("0.80")


@define(frozen=True, slots=True)
class CategoryGroupBudgetStatus:
    # None for the synthetic "Uncategorized" row (spending in categories
    # with no group mapping) — it has no CategoryGroup entity behind it and
    # can never carry a budget.
    group_id: UUID | None
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
    budgeted_months: int
    household_spending: Decimal | None = None
    personal_spending: Decimal | None = None
    # Same per-category breakdown as `categories`, but computed over the YTD
    # window — includes categories with spend in earlier months that have
    # none in the currently viewed month (v1.7.2).
    ytd_categories: list[CategoryBreakdown] = Factory(list[CategoryBreakdown])


@define(frozen=True, slots=True)
class BudgetOverview:
    year: int
    month: int
    group_statuses: list[CategoryGroupBudgetStatus]
    total_monthly_budget: Decimal
    total_monthly_spent: Decimal
    total_ytd_budget: Decimal
    total_ytd_spent: Decimal
    spending_drift: Decimal | None = None


def determine_health(spent: Decimal, budget: Decimal) -> HealthStatus:
    if budget <= 0:
        return "over_budget" if spent > 0 else "on_track"
    ratio = spent / budget
    if ratio > 1:
        return "over_budget"
    if ratio >= _NEAR_LIMIT_THRESHOLD:
        return "near_limit"
    return "on_track"


def compute_average_monthly_spending(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    through_month: int,
    lens: SpendingLens = HOUSEHOLD_LENS,
) -> dict[UUID, Decimal]:
    """Average per group, divided by the number of months through
    `through_month` with any row under the lens (any group, expense or
    refund). Months with no rows — typically not yet uploaded — do not
    dilute the average; a refund-only month does count as a month.
    Refunds net, like every other spending figure."""
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in select(lens, year_txs):
        if tx.date.month <= through_month:
            by_month[tx.date.month].append(tx)

    group_totals: dict[UUID, Decimal] = defaultdict(Decimal)
    for txs in by_month.values():
        for bd in compute_breakdowns(lens, txs, category_lookup):
            if bd.group_id is not None:
                group_totals[bd.group_id] += bd.total_amount

    num_months = len(by_month) or 1
    return {gid: total / num_months for gid, total in group_totals.items()}


def _totals_drift(
    status_total: Decimal,
    by_group: dict[UUID | None, CategoryGroupBreakdown],
    mapped_ids: set[UUID | None],
) -> Decimal:
    breakdown_total = sum(
        (bd.total_amount for gid, bd in by_group.items() if gid in mapped_ids),
        Decimal(0),
    )
    return status_total - breakdown_total


def _check_spending_integrity(
    statuses: list[CategoryGroupBudgetStatus],
    month_by_group: dict[UUID | None, CategoryGroupBreakdown],
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown],
) -> Decimal | None:
    """Return the spending drift amount, or None if totals are consistent."""
    # None (unmapped/Uncategorized) always counts as "accounted for" here —
    # whether or not a synthetic Uncategorized status exists, its spend must
    # not be silently dropped from the drift comparison.
    mapped_ids: set[UUID | None] = {s.group_id for s in statuses} | {None}
    drift = _totals_drift(
        sum((s.monthly_spent for s in statuses), Decimal(0)),
        month_by_group,
        mapped_ids,
    ) + _totals_drift(
        sum((s.ytd_spent for s in statuses), Decimal(0)),
        ytd_by_group,
        mapped_ids,
    )
    return drift if drift != Decimal(0) else None


def _index_month_budgets(
    month_budgets: list[CategoryGroupBudget],
) -> dict[UUID, CategoryGroupBudget]:
    return {b.group_id: b for b in month_budgets}


@define(frozen=True, slots=True)
class _GroupStatusContext:
    """Shared, per-overview-computation context for building one group's
    status. Bundled so `_build_group_status` and
    `_uncategorized_status_if_present` take a fixed small arg list instead
    of forwarding the same six values individually."""

    month_budget_index: dict[UUID, CategoryGroupBudget]
    year_budgets: list[CategoryGroupBudget]
    month_by_group: dict[UUID | None, CategoryGroupBreakdown]
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown]
    avg_spending: dict[UUID, Decimal]
    month: int


def _build_group_status(
    gid: UUID | None,
    name: str,
    ctx: _GroupStatusContext,
) -> CategoryGroupBudgetStatus:
    # gid is None only for the synthetic Uncategorized row — it has no
    # CategoryGroup entity, so it can never carry a budget or an average.
    effective = ctx.month_budget_index.get(gid) if gid is not None else None

    monthly_bd = ctx.month_by_group.get(gid)
    ytd_bd = ctx.ytd_by_group.get(gid)
    monthly_spent = monthly_bd.total_amount if monthly_bd else Decimal(0)
    ytd_spent = ytd_bd.total_amount if ytd_bd else Decimal(0)

    monthly_budget = effective.monthly_amount if effective else None
    budgets_through_month = [
        b for b in ctx.year_budgets if b.group_id == gid and b.month <= ctx.month
    ]
    ytd_budget_val = (
        sum((b.monthly_amount for b in budgets_through_month), Decimal(0))
        if budgets_through_month
        else None
    )

    household_spend, personal_spend = (
        source_split([monthly_bd]) if monthly_bd else (Decimal(0), Decimal(0))
    )

    return CategoryGroupBudgetStatus(
        group_id=gid,
        group_name=name,
        budget_id=effective.id if effective else None,
        monthly_budget=monthly_budget,
        monthly_spent=monthly_spent,
        ytd_budget=ytd_budget_val,
        ytd_spent=ytd_spent,
        monthly_health=determine_health(monthly_spent, monthly_budget)
        if monthly_budget is not None
        else None,
        ytd_health=determine_health(ytd_spent, ytd_budget_val)
        if ytd_budget_val is not None
        else None,
        average_monthly_spending=(
            ctx.avg_spending.get(gid, Decimal(0)) if gid is not None else Decimal(0)
        ),
        categories=monthly_bd.categories if monthly_bd else [],
        ytd_categories=ytd_bd.categories if ytd_bd else [],
        budgeted_months=len(budgets_through_month),
        household_spending=household_spend,
        personal_spending=personal_spend,
    )


def _uncategorized_status_if_present(
    ctx: _GroupStatusContext,
) -> CategoryGroupBudgetStatus | None:
    """Synthesize the Uncategorized row when spending exists in categories
    with no group mapping — otherwise that spend vanishes from every status
    and grand total (v1.7.2). Never budgetable: group_id=None has no
    CategoryGroup entity behind it."""
    if None not in ctx.month_by_group and None not in ctx.ytd_by_group:
        return None
    return _build_group_status(None, UNCATEGORIZED_GROUP_NAME, ctx)


def _assemble_overview(
    statuses: list[CategoryGroupBudgetStatus],
    year: int,
    month: int,
    spending_drift: Decimal | None = None,
) -> BudgetOverview:
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
        # YTD totals span every group with a YTD budget OR YTD spend — not
        # just groups budgeted in the *viewed* month. A group budgeted
        # Jan-Feb but not the viewed March still contributes its YTD spend
        # and budget; otherwise its own row would outrun the Total (US-BUDGET-3).
        total_ytd_budget=sum(
            (s.ytd_budget for s in statuses if s.ytd_budget is not None), Decimal(0)
        ),
        total_ytd_spent=sum(
            (
                s.ytd_spent
                for s in statuses
                if s.ytd_budget is not None or s.ytd_spent != Decimal(0)
            ),
            Decimal(0),
        ),
        spending_drift=spending_drift,
    )


@define(frozen=True, slots=True)
class BudgetOverviewInputs:
    """Inputs to `compute_budget_overview`, bundled to keep its signature small."""

    month_budgets: list[CategoryGroupBudget]
    year_budgets: list[CategoryGroupBudget]
    year_txs: list[Transaction]
    category_lookup: dict[str, tuple[UUID, str]]
    groups: list[CategoryGroup]
    year: int
    month: int


def _budgetable_group_names(groups: list[CategoryGroup]) -> dict[UUID, str]:
    """Transfer groups are money movement: no status row, no budget."""
    return {g.id: g.name for g in groups if is_spending_kind(g.kind)}


def compute_budget_overview(
    inputs: BudgetOverviewInputs,
    lens: SpendingLens = HOUSEHOLD_LENS,
) -> BudgetOverview:
    """Budget status per group under a lens: the household's spending, or
    one person's share (`PersonalLens`). Transfer groups get no row."""
    group_names = _budgetable_group_names(inputs.groups)

    ytd_txs = [
        tx for tx in select(lens, inputs.year_txs) if tx.date.month <= inputs.month
    ]
    month_txs = [tx for tx in ytd_txs if tx.date.month == inputs.month]

    month_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd
        for bd in compute_breakdowns(lens, month_txs, inputs.category_lookup)
    }
    ytd_by_group: dict[UUID | None, CategoryGroupBreakdown] = {
        bd.group_id: bd
        for bd in compute_breakdowns(lens, ytd_txs, inputs.category_lookup)
    }

    avg_spending = compute_average_monthly_spending(
        inputs.year_txs, inputs.category_lookup, inputs.month, lens
    )

    ctx = _GroupStatusContext(
        month_budget_index=_index_month_budgets(inputs.month_budgets),
        year_budgets=inputs.year_budgets,
        month_by_group=month_by_group,
        ytd_by_group=ytd_by_group,
        avg_spending=avg_spending,
        month=inputs.month,
    )

    statuses: list[CategoryGroupBudgetStatus] = [
        _build_group_status(gid, name, ctx) for gid, name in group_names.items()
    ]
    uncategorized = _uncategorized_status_if_present(ctx)
    if uncategorized is not None:
        statuses.append(uncategorized)

    drift = _check_spending_integrity(statuses, month_by_group, ytd_by_group)
    return _assemble_overview(statuses, inputs.year, inputs.month, spending_drift=drift)


def find_copyable_source(
    all_budgets: list[CategoryGroupBudget],
    year: int,
    month: int,
) -> tuple[int, int] | None:
    """Most recent (year, month) with budgets strictly before the given month."""
    best: tuple[int, int] | None = None
    for b in all_budgets:
        ym = (b.year, b.month)
        if ym < (year, month) and (best is None or ym > best):
            best = ym
    return best


def has_budgets_for_month(
    all_budgets: list[CategoryGroupBudget],
    year: int,
    month: int,
) -> bool:
    """Check whether any budget exists for the given month."""
    return any(b.year == year and b.month == month for b in all_budgets)
