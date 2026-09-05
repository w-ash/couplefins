"""Search transactions with merchant/category/tag filters.

Thin use case wrapping the repository's date-range query with in-memory
filtering for the chat assistant's search_transactions tool.
"""

from uuid import UUID

from attrs import define, field

from src.application.use_cases._shared.command_validators import (
    Scope,
    month_range,
    positive_int,
    require_person_for_personal_scope,
)
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
    load_reconciliation_context,
)
from src.application.use_cases._shared.transaction_reads import (
    fetch_listed_rows,
    fetch_scoped_rows,
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
    scope: Scope = "all"
    person_id: UUID | None = None
    limit: int = _DEFAULT_LIMIT

    def __attrs_post_init__(self) -> None:
        require_person_for_personal_scope(self.scope, self.person_id)


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
            window = month_bounds(command.year, command.month)
            tags = (command.tag,) if command.tag else None

            ctx: ReconciliationContext | None = None
            if command.scope == "all":
                txns = await fetch_listed_rows(uow, window, tags=tags)
            else:
                # Spending scopes never list money movement; "all" keeps it
                # visible — the same rule as the Transactions page.
                ctx = await load_reconciliation_context(uow)
                txns = (
                    await fetch_scoped_rows(
                        uow, ctx, window, command.scope, command.person_id, tags=tags
                    )
                ).spending

            if command.merchant:
                needle = command.merchant.lower()
                txns = [t for t in txns if needle in t.merchant.lower()]

            if command.category_group_id:
                mappings = (
                    ctx.categories
                    if ctx is not None
                    else await uow.categories.get_all()
                )
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
