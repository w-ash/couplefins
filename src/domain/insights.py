from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.categories import compute_category_breakdowns
from src.domain.entities.transaction import Transaction


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
) -> SpendingTrends:
    shared_expenses = [tx for tx in year_txs if tx.is_shared and tx.amount < 0]

    by_month: dict[int, list[Transaction]] = defaultdict(list)
    for tx in shared_expenses:
        by_month[tx.date.month].append(tx)

    monthly_group_spending: list[MonthlyGroupSpending] = []
    monthly_totals: list[MonthlyTotal] = []
    group_ytd: dict[UUID | None, Decimal] = defaultdict(Decimal)
    group_counts: dict[UUID | None, int] = defaultdict(int)
    group_names: dict[UUID | None, str] = {}

    for month in sorted(by_month):
        breakdowns = compute_category_breakdowns(by_month[month], category_lookup)
        month_total = Decimal(0)
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
