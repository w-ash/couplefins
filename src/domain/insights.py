from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.categories import compute_category_breakdowns
from src.domain.entities.transaction import Transaction
from src.domain.filters import is_reconciliation_relevant


def _household_expenses(txs: list[Transaction]) -> list[Transaction]:
    return [
        tx
        for tx in txs
        if tx.household and tx.amount < 0 and is_reconciliation_relevant(tx)
    ]


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
class MonthlySettlement:
    year: int
    month: int
    amount: Decimal
    from_person_id: UUID
    to_person_id: UUID
    is_settled: bool
    # Ledger-derived: settled | partially_settled | carried_forward
    status: str


@define(frozen=True, slots=True)
class CategorySpending:
    category: str
    amount: Decimal


@define(frozen=True, slots=True)
class MonthlyPersonPaid:
    month: int
    person_id: UUID
    group_id: UUID | None
    amount_paid: Decimal


@define(frozen=True, slots=True)
class MonthlyGroupSpending:
    year: int
    month: int
    group_id: UUID | None
    group_name: str
    amount: Decimal
    categories: list[CategorySpending]


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
) -> SpendingTrends:
    """Compute per-month trends (full year) and YTD group summaries.

    `monthly_group_spending`/`monthly_totals` cover every month present in
    `year_txs` — the "Spending by category" sparklines want the whole
    year's shape. `group_summaries.ytd_total` is bounded at `through_month`
    when given (the selected month), so "Year to date" agrees with Budget
    and Dashboard's YTD instead of silently including months after the
    one being viewed.
    """
    by_month = _group_by_month(_household_expenses(year_txs))

    monthly_group_spending: list[MonthlyGroupSpending] = []
    monthly_totals: list[MonthlyTotal] = []
    group_ytd: dict[UUID | None, Decimal] = defaultdict(Decimal)
    group_counts: dict[UUID | None, int] = defaultdict(int)
    group_names: dict[UUID | None, str] = {}

    for month in sorted(by_month):
        breakdowns = compute_category_breakdowns(by_month[month], category_lookup)
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
                    categories=[
                        CategorySpending(category=cat.category, amount=cat.total_amount)
                        for cat in bd.categories
                    ],
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
    window: int = 3,
) -> dict[UUID | None, Decimal]:
    by_month = _group_by_month(expenses)

    prior_months = sorted(m for m in by_month if m < target_month)
    trailing_months = prior_months[-window:]
    if not trailing_months:
        return {}

    group_totals: dict[UUID | None, Decimal] = defaultdict(Decimal)
    for month in trailing_months:
        for bd in compute_category_breakdowns(by_month[month], category_lookup):
            group_totals[bd.group_id] += bd.total_amount

    num_months = len(trailing_months)
    return {gid: total / num_months for gid, total in group_totals.items()}


def compute_trailing_average(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int = 3,
) -> dict[UUID | None, Decimal]:
    return _compute_trailing_average_from_expenses(
        _household_expenses(year_txs), category_lookup, target_month, window
    )


def compute_comparison_cards(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    target_month: int,
    window: int = 3,
) -> list[GroupComparison]:
    expenses = _household_expenses(year_txs)
    target_txs = [tx for tx in expenses if tx.date.month == target_month]

    current_by_group: dict[UUID | None, tuple[str, Decimal]] = {}
    for bd in compute_category_breakdowns(target_txs, category_lookup):
        current_by_group[bd.group_id] = (bd.group_name, bd.total_amount)

    trailing_avg = _compute_trailing_average_from_expenses(
        expenses, category_lookup, target_month, window
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


def compute_person_paid_by_month(
    year_txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
) -> list[MonthlyPersonPaid]:
    """Per-person paid amounts grouped by month and category group."""
    expenses = _household_expenses(year_txs)
    totals: dict[tuple[int, UUID, UUID | None], Decimal] = defaultdict(Decimal)

    for tx in expenses:
        group_id: UUID | None = None
        cat_entry = category_lookup.get(tx.category)
        if cat_entry is not None:
            group_id = cat_entry[0]
        key = (tx.date.month, tx.payer_person_id, group_id)
        totals[key] += abs(tx.amount)

    return [
        MonthlyPersonPaid(
            month=month,
            person_id=pid,
            group_id=gid,
            amount_paid=amount,
        )
        for (month, pid, gid), amount in sorted(
            totals.items(), key=lambda t: (t[0][0], str(t[0][1]), str(t[0][2]))
        )
    ]
