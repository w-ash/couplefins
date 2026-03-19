from src.application.use_cases._shared.date_math import month_bounds
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
)
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import ReconciliationSummary, reconcile


def reconcile_all_months(
    by_month: dict[int, list[Transaction]],
    ctx: ReconciliationContext,
    year: int,
) -> dict[int, ReconciliationSummary]:
    results: dict[int, ReconciliationSummary] = {}
    for month, txs in by_month.items():
        start, end = month_bounds(year, month)
        results[month] = reconcile(
            txs,
            ctx.persons,
            ctx.categories,
            ctx.category_groups,
            start_date=start,
            end_date=end,
        )
    return results
