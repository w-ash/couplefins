"""Search transactions with merchant/category/tag filters.

Thin use case wrapping the repository's date-range query with in-memory
filtering for the chat assistant's search_transactions tool.
"""

from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    month_range,
    positive_int,
)
from src.domain.date_math import month_bounds
from src.domain.entities.transaction import Transaction
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

_DEFAULT_LIMIT = 20


@define(frozen=True, slots=True)
class SearchTransactionsCommand:
    year: int = field(validator=positive_int)
    month: int = field(validator=month_range)
    merchant: str | None = None
    category_group_id: UUID | None = None
    tag: str | None = None
    limit: int = _DEFAULT_LIMIT


@define(frozen=True, slots=True)
class SearchTransactionsResult:
    transactions: list[Transaction]
    total_count: int


@define(slots=True)
class SearchTransactionsUseCase:
    async def execute(
        self,
        command: SearchTransactionsCommand,
        uow: UnitOfWorkProtocol,
    ) -> SearchTransactionsResult:
        async with uow:
            start, end = month_bounds(command.year, command.month)

            tags = (command.tag,) if command.tag else None
            txns = await uow.transactions.get_household_by_date_range(
                start, end, tags=tags
            )

            if command.merchant:
                needle = command.merchant.lower()
                txns = [t for t in txns if needle in t.merchant.lower()]

            if command.category_group_id:
                mappings = await uow.categories.get_all()
                matching_categories = {
                    c.name for c in mappings if c.group_id == command.category_group_id
                }
                txns = [t for t in txns if t.category in matching_categories]

            txns.sort(key=lambda t: t.date, reverse=True)
            total = len(txns)
            return SearchTransactionsResult(
                transactions=txns[: command.limit],
                total_count=total,
            )
