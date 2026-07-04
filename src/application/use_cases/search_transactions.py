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
)
from src.domain.date_math import month_bounds
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import ValidationError
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
        if self.scope == "personal" and self.person_id is None:
            raise ValidationError("person_id is required for personal scope")


@define(frozen=True, slots=True)
class SearchTransactionsResult:
    transactions: list[Transaction]
    total_count: int


def _matches_tag(tx: Transaction, tag: str) -> bool:
    needle = tag.lower()
    return needle in {t.lower() for t in tx.tags}


@define(slots=True)
class SearchTransactionsUseCase:
    async def execute(
        self,
        command: SearchTransactionsCommand,
        uow: UnitOfWorkProtocol,
    ) -> SearchTransactionsResult:
        async with uow:
            start, end = month_bounds(command.year, command.month)

            if command.scope == "household":
                txns = await uow.transactions.get_household_by_date_range(start, end)
            elif command.scope == "personal":
                person_id = command.person_id
                if person_id is None:
                    raise ValidationError("person_id is required for personal scope")
                txns = await uow.transactions.get_by_person_and_date_range(
                    person_id, start, end
                )
            else:
                txns = await uow.transactions.get_by_date_range(start, end)

            if command.tag:
                txns = [t for t in txns if _matches_tag(t, command.tag)]

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
