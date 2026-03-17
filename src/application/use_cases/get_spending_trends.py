from attrs import define, field

from src.application.use_cases._shared.command_validators import positive_int
from src.application.use_cases._shared.reconciliation_context import (
    load_reconciliation_context,
)
from src.domain.categories import build_category_lookup
from src.domain.insights import SpendingTrends, compute_spending_trends
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


@define(frozen=True, slots=True)
class GetSpendingTrendsCommand:
    year: int = field(validator=positive_int)


@define(frozen=True, slots=True)
class GetSpendingTrendsResult:
    year: int
    trends: SpendingTrends


@define(slots=True)
class GetSpendingTrendsUseCase:
    async def execute(
        self, command: GetSpendingTrendsCommand, uow: UnitOfWorkProtocol
    ) -> GetSpendingTrendsResult:
        async with uow:
            ctx = await load_reconciliation_context(uow)
            year_txs = await uow.transactions.get_shared_by_year(command.year)
            category_lookup = build_category_lookup(
                ctx.category_mappings, ctx.category_groups
            )
            trends = compute_spending_trends(year_txs, category_lookup, command.year)
            return GetSpendingTrendsResult(year=command.year, trends=trends)
