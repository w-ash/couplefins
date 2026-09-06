from collections import defaultdict
from collections.abc import Container
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.constants import UNCATEGORIZED_GROUP_NAME
from src.domain.entities.transaction import Transaction
from src.domain.spending_lens import (
    FlowSourceKind,
    HouseholdLens,
    PersonalLens,
    SpendingLens,
    compute_breakdowns,
    select,
)


def _lens(person_id: UUID | None) -> SpendingLens:
    """Household lens, or one person's share of spending."""
    return HouseholdLens() if person_id is None else PersonalLens(person_id)


def _group_by_month(txs: list[Transaction]) -> dict[int, list[Transaction]]:
    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in txs:
        by_month[tx.date.month].append(tx)
    return by_month


def _build_group_name_lookup(
    category_lookup: dict[str, tuple[UUID, str]],
) -> dict[UUID | None, str]:
    names: dict[UUID | None, str] = dict(category_lookup.values())
    names[None] = "Uncategorized"
    return names


@define(frozen=True, slots=True)
class GroupComparison:
    group_id: UUID | None
    group_name: str
    current_month_amount: Decimal
    trailing_average: Decimal
    delta_amount: Decimal
    delta_percentage: Decimal
    is_new: bool


@define(frozen=True, slots=True)
class CategoryComparison:
    category: str
    group_id: UUID | None
    group_name: str
    current_month_amount: Decimal
    trailing_average: Decimal
    delta_amount: Decimal
    delta_percentage: Decimal
    is_new: bool


@define(frozen=True, slots=True)
class SpendingFlowCell:
    """One (source, category) sum under the lens: the flow chart's atom.
    `source_person_id` is the payer; `source_kind` says what claim the
    viewer has on the row (see `SpendingLens.flow_source`)."""

    source_kind: FlowSourceKind
    source_person_id: UUID
    group_id: UUID | None
    group_name: str
    category: str
    amount: Decimal
    transaction_count: int


@define(frozen=True, slots=True)
class TopMerchant:
    merchant: str
    amount: Decimal
    transaction_count: int
    category: str
    group_id: UUID | None


@define(frozen=True, slots=True)
class SpendingFlow:
    """Where a period's money went: flow cells plus the merchants that
    dominated it. Every amount is the lens contribution (expense positive,
    refund negative), so cells sum to the period's spending."""

    cells: list[SpendingFlowCell]
    top_merchants: list[TopMerchant]


@define(frozen=True, slots=True)
class MonthlyGroupSpending:
    year: int
    month: int
    group_id: UUID | None
    group_name: str
    amount: Decimal


@define(frozen=True, slots=True)
class MonthlyTotal:
    year: int
    month: int
    total_amount: Decimal


@define(frozen=True, slots=True)
class GroupSummary:
    group_id: UUID | None
    group_name: str
    ytd_total: Decimal
    transaction_count: int


@define(frozen=True, slots=True)
class SpendingTrends:
    monthly_group_spending: list[MonthlyGroupSpending]
    monthly_totals: list[MonthlyTotal]
    group_summaries: list[GroupSummary]


def compute_spending_trends(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    year: int,
    through_month: int | None = None,
    *,
    person_id: UUID | None = None,
) -> SpendingTrends:
    """Compute per-month trends (full year) and YTD group summaries.

    `monthly_group_spending`/`monthly_totals` cover every month present in
    `year_txs` — the "Spending by category" sparklines want the whole
    year's shape. `group_summaries.ytd_total` is bounded at `through_month`
    when given (the selected month), so "Year to date" agrees with Budget
    and Dashboard's YTD instead of silently including months after the
    one being viewed. `person_id` switches to that person's share of
    spending (`PersonalLens`).
    """
    lens = _lens(person_id)
    by_month = _group_by_month(select(lens, year_txs))

    monthly_group_spending: list[MonthlyGroupSpending] = []
    monthly_totals: list[MonthlyTotal] = []
    group_ytd: dict[UUID | None, Decimal] = defaultdict(Decimal)
    group_counts: dict[UUID | None, int] = defaultdict(int)
    group_names: dict[UUID | None, str] = {}

    for month in sorted(by_month):
        breakdowns = compute_breakdowns(lens, by_month[month], category_lookup)
        month_total = Decimal(0)
        within_ytd = through_month is None or month <= through_month
        for bd in breakdowns:
            monthly_group_spending.append(
                MonthlyGroupSpending(
                    year=year,
                    month=month,
                    group_id=bd.group_id,
                    group_name=bd.group_name,
                    amount=bd.total_amount,
                )
            )
            month_total += bd.total_amount
            if within_ytd:
                group_ytd[bd.group_id] += bd.total_amount
                group_counts[bd.group_id] += bd.transaction_count
            group_names[bd.group_id] = bd.group_name

        monthly_totals.append(
            MonthlyTotal(year=year, month=month, total_amount=month_total)
        )

    group_summaries = sorted(
        [
            GroupSummary(
                group_id=gid,
                group_name=group_names[gid],
                ytd_total=group_ytd[gid],
                transaction_count=group_counts[gid],
            )
            for gid in group_ytd
        ],
        key=lambda g: g.ytd_total,
        reverse=True,
    )

    return SpendingTrends(
        monthly_group_spending=monthly_group_spending,
        monthly_totals=monthly_totals,
        group_summaries=group_summaries,
    )


def _compute_trailing_average_from_expenses(
    expenses: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int,
    lens: SpendingLens,
) -> dict[UUID | None, Decimal]:
    by_month = _group_by_month(expenses)

    prior_months = sorted(m for m in by_month if m < target_month)
    trailing_months = prior_months[-window:]
    if not trailing_months:
        return {}

    group_totals: dict[UUID | None, Decimal] = defaultdict(Decimal)
    for month in trailing_months:
        for bd in compute_breakdowns(lens, by_month[month], category_lookup):
            group_totals[bd.group_id] += bd.total_amount

    num_months = len(trailing_months)
    return {gid: total / num_months for gid, total in group_totals.items()}


def compute_trailing_average(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int = 3,
    *,
    person_id: UUID | None = None,
) -> dict[UUID | None, Decimal]:
    lens = _lens(person_id)
    return _compute_trailing_average_from_expenses(
        select(lens, year_txs), category_lookup, target_month, window, lens
    )


def compute_comparison_cards(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int = 3,
    *,
    person_id: UUID | None = None,
) -> list[GroupComparison]:
    lens = _lens(person_id)
    expenses = select(lens, year_txs)
    target_txs = [tx for tx in expenses if tx.date.month == target_month]

    current_by_group: dict[UUID | None, tuple[str, Decimal]] = {}
    for bd in compute_breakdowns(lens, target_txs, category_lookup):
        current_by_group[bd.group_id] = (bd.group_name, bd.total_amount)

    trailing_avg = _compute_trailing_average_from_expenses(
        expenses, category_lookup, target_month, window, lens
    )

    group_names = _build_group_name_lookup(category_lookup)
    all_group_ids = set(current_by_group) | set(trailing_avg)
    cards: list[GroupComparison] = []
    for gid in all_group_ids:
        current_name, current_amount = current_by_group.get(gid, ("", Decimal(0)))
        avg = trailing_avg.get(gid, Decimal(0))

        if not current_name:
            current_name = group_names.get(gid, "Unknown")

        is_new = avg == 0
        delta = current_amount - avg
        pct = (delta / avg * 100) if avg > 0 else Decimal(0)

        cards.append(
            GroupComparison(
                group_id=gid,
                group_name=current_name,
                current_month_amount=current_amount,
                trailing_average=avg,
                delta_amount=delta,
                delta_percentage=pct,
                is_new=is_new,
            )
        )

    # A brand-new group (no trailing average) has an undefined percentage
    # change — treat it as the most significant kind of swing (ranks above
    # any finite percentage) and break ties among new groups by dollar
    # delta, since percentage is meaningless when the baseline is zero.
    cards.sort(
        key=lambda c: (
            c.is_new,
            abs(c.delta_amount if c.is_new else c.delta_percentage),
        ),
        reverse=True,
    )
    return cards


def _group_of(
    category_lookup: dict[str, tuple[UUID, str]], category: str
) -> tuple[UUID | None, str]:
    return category_lookup.get(category, (None, UNCATEGORIZED_GROUP_NAME))


def _dominant_category(amount_by_category: dict[str, Decimal]) -> str:
    return max(amount_by_category, key=amount_by_category.__getitem__)


def compute_spending_flow(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    *,
    person_id: UUID | None = None,
    months: Container[int],
    merchant_limit: int = 10,
) -> SpendingFlow:
    """Where the money went in `months` (one month, or January through the
    selected month for year to date), under the household or a person's lens.
    Cells sort by group total, then amount, so the largest flows come first."""
    lens = _lens(person_id)
    rows = [tx for tx in select(lens, year_txs) if tx.date.month in months]

    cell_amount: dict[tuple[FlowSourceKind, UUID, str], Decimal] = defaultdict(Decimal)
    cell_count: dict[tuple[FlowSourceKind, UUID, str], int] = defaultdict(int)
    merchant_amount: dict[str, Decimal] = defaultdict(Decimal)
    merchant_count: dict[str, int] = defaultdict(int)
    merchant_categories: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )
    group_total: dict[UUID | None, Decimal] = defaultdict(Decimal)

    for tx in rows:
        amount = lens.contribution(tx)
        source = lens.flow_source(tx)
        key = (source.kind, source.person_id, tx.category)
        cell_amount[key] += amount
        cell_count[key] += 1
        merchant_amount[tx.merchant] += amount
        merchant_count[tx.merchant] += 1
        merchant_categories[tx.merchant][tx.category] += amount
        group_total[_group_of(category_lookup, tx.category)[0]] += amount

    cells = [
        SpendingFlowCell(
            source_kind=kind,
            source_person_id=pid,
            group_id=gid,
            group_name=gname,
            category=category,
            amount=amount,
            transaction_count=cell_count[kind, pid, category],
        )
        for (kind, pid, category), amount in cell_amount.items()
        for gid, gname in [_group_of(category_lookup, category)]
    ]
    cells.sort(
        key=lambda c: (-group_total[c.group_id], c.group_name, -c.amount, c.category)
    )

    top_merchants = [
        TopMerchant(
            merchant=merchant,
            amount=amount,
            transaction_count=merchant_count[merchant],
            category=dominant,
            group_id=_group_of(category_lookup, dominant)[0],
        )
        for merchant, amount in sorted(
            merchant_amount.items(), key=lambda m: (-m[1], m[0])
        )
        if amount > 0
        for dominant in [_dominant_category(merchant_categories[merchant])]
    ][:merchant_limit]

    return SpendingFlow(
        cells=cells,
        top_merchants=top_merchants,
    )


def _category_totals(
    lens: SpendingLens,
    txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
) -> dict[str, Decimal]:
    return {
        cat.category: cat.total_amount
        for bd in compute_breakdowns(lens, txs, category_lookup)
        for cat in bd.categories
    }


def compute_category_comparisons(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int = 3,
    *,
    person_id: UUID | None = None,
) -> list[CategoryComparison]:
    """`compute_comparison_cards` at category grain: the target month against
    the trailing-window average per category, biggest swings first (a new
    category outranks any finite percentage, ties broken by dollars)."""
    lens = _lens(person_id)
    by_month = _group_by_month(select(lens, year_txs))
    current = _category_totals(lens, by_month.get(target_month, []), category_lookup)

    trailing_months = sorted(m for m in by_month if m < target_month)[-window:]
    trailing_sum: dict[str, Decimal] = defaultdict(Decimal)
    for month in trailing_months:
        for cat, amount in _category_totals(
            lens, by_month[month], category_lookup
        ).items():
            trailing_sum[cat] += amount
    trailing_avg = {
        cat: total / len(trailing_months) for cat, total in trailing_sum.items()
    }

    comparisons: list[CategoryComparison] = []
    for cat in set(current) | set(trailing_avg):
        amount = current.get(cat, Decimal(0))
        avg = trailing_avg.get(cat, Decimal(0))
        gid, gname = _group_of(category_lookup, cat)
        delta = amount - avg
        comparisons.append(
            CategoryComparison(
                category=cat,
                group_id=gid,
                group_name=gname,
                current_month_amount=amount,
                trailing_average=avg,
                delta_amount=delta,
                delta_percentage=(delta / avg * 100) if avg > 0 else Decimal(0),
                is_new=avg == 0,
            )
        )
    comparisons.sort(
        key=lambda c: (
            c.is_new,
            abs(c.delta_amount if c.is_new else c.delta_percentage),
            c.category,
        ),
        reverse=True,
    )
    return comparisons
