"""The only place use cases read transaction lists.

Each function names the rows it returns. Where rows feed money math, the
transfer rule (`exclude_transfers`) is applied here, once, so a use case
cannot forget it. A grep gate in tests/unit/application/test_transaction_reads.py
forbids list reads on `uow.transactions` anywhere else under src/application.
"""

from datetime import date
from uuid import UUID

from attrs import define

from src.application.use_cases._shared.command_validators import Scope
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
)
from src.domain.entities.transaction import Transaction
from src.domain.filters import exclude_transfers
from src.domain.person_spending import compute_person_share
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol

type DateWindow = tuple[date, date]


@define(frozen=True, slots=True)
class ScopedRows:
    """One fetch, two views. `listed` keeps transfer rows (the Transactions
    page shows them with a badge); `spending` drops them for the math."""

    listed: list[Transaction]
    spending: list[Transaction]


async def fetch_year_spending_rows(
    uow: UnitOfWorkProtocol, year: int, scope: Scope, ctx: ReconciliationContext
) -> list[Transaction]:
    """A year's rows for a spending page. Household scope needs only
    household rows; a person's lens (and "all") also reads personal and
    spotted rows, so it takes the whole year."""
    if scope == "household":
        txs = await uow.transactions.get_household_by_year(year)
    else:
        txs = await uow.transactions.get_by_year(year)
    return exclude_transfers(txs, ctx.transfer_categories)


async def fetch_all_settlement_rows(
    uow: UnitOfWorkProtocol, ctx: ReconciliationContext
) -> list[Transaction]:
    """Every settlement-relevant row, all time — the ledger's input."""
    return exclude_transfers(
        await uow.transactions.get_all_settlement_relevant(), ctx.transfer_categories
    )


async def fetch_settlement_rows(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
    window: DateWindow,
    *,
    tags: tuple[str, ...] | None = None,
) -> list[Transaction]:
    """Settlement-relevant rows in a date window."""
    start, end = window
    return exclude_transfers(
        await uow.transactions.get_settlement_relevant_by_date_range(
            start, end, tags=tags
        ),
        ctx.transfer_categories,
    )


async def fetch_scoped_rows(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
    window: DateWindow,
    scope: Scope,
    person_id: UUID | None = None,
    *,
    tags: tuple[str, ...] | None = None,
) -> ScopedRows:
    """Rows for a scoped list page. Personal = every row where the person's
    share is positive (`PersonalLens`): their share of household splits,
    their own personal rows, and what their partner spotted for them — so
    the list sums to the Insights and Dashboard "my spending" figure.
    "all" with a person = household rows plus that person's own personal rows."""
    start, end = window
    if scope == "personal" and person_id is not None:
        window_txs = await uow.transactions.get_by_date_range(start, end, tags=tags)
        listed = [tx for tx in window_txs if compute_person_share(tx, person_id) > 0]
    elif scope == "all" and person_id is not None:
        household_txs = await uow.transactions.get_household_by_date_range(
            start, end, tags=tags
        )
        person_txs = await uow.transactions.get_by_person_and_date_range(
            person_id, start, end, tags=tags
        )
        household_ids = {tx.id for tx in household_txs}
        listed = household_txs + [
            tx for tx in person_txs if not tx.household and tx.id not in household_ids
        ]
    else:
        listed = await uow.transactions.get_household_by_date_range(
            start, end, tags=tags
        )
    return ScopedRows(
        listed=listed, spending=exclude_transfers(listed, ctx.transfer_categories)
    )


async def fetch_latest_spending_month(
    uow: UnitOfWorkProtocol, ctx: ReconciliationContext
) -> tuple[int, int] | None:
    """(year, month) of the newest household spending row, or None. Transfer
    rows are excluded so a card payment cannot point at an empty month."""
    latest = await uow.transactions.get_latest_household_transaction_date(
        excluding_categories=ctx.transfer_categories
    )
    return (latest.year, latest.month) if latest else None


async def fetch_listed_rows(
    uow: UnitOfWorkProtocol,
    window: DateWindow,
    *,
    tags: tuple[str, ...] | None = None,
) -> list[Transaction]:
    """Every row in a window, transfers included. For the All list and
    settlement-candidate search (Venmo legs live in the Transfer group) —
    takes no context so it cannot be "fixed" by accident."""
    start, end = window
    return await uow.transactions.get_by_date_range(start, end, tags=tags)
