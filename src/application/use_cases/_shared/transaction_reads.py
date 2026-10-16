"""The only place use cases read transaction lists.

Each function names the rows it returns. Where rows feed money math, the
transfer rule (`exclude_non_spending`) is applied here, once, so a use case
cannot forget it. A grep gate in tests/unit/application/test_transaction_reads.py
forbids list reads on `uow.transactions` anywhere else under src/application.
"""

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from attrs import define
from structlog.stdlib import get_logger

from src.application.use_cases._shared.command_validators import Scope
from src.application.use_cases._shared.reconciliation_context import (
    ReconciliationContext,
)
from src.domain.entities.category_group import is_spending_kind
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.filters import depositor_of, exclude_non_spending
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol
from src.domain.splits import owner_shares, person_share, share_amounts

logger = get_logger()

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
    return exclude_non_spending(txs, ctx.non_spending_categories)


async def fetch_all_settlement_rows(
    uow: UnitOfWorkProtocol, ctx: ReconciliationContext
) -> list[Transaction]:
    """Every settlement-relevant row, all time — the ledger's input."""
    return exclude_non_spending(
        await uow.transactions.get_all_settlement_relevant(),
        ctx.non_spending_categories,
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
    return exclude_non_spending(
        await uow.transactions.get_settlement_relevant_by_date_range(
            start, end, tags=tags
        ),
        ctx.non_spending_categories,
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
        listed = [
            tx for tx in window_txs if person_share(tx, person_id, ctx.person_ids) > 0
        ]
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
        listed=listed,
        spending=exclude_non_spending(listed, ctx.non_spending_categories),
    )


async def fetch_latest_spending_month(
    uow: UnitOfWorkProtocol, ctx: ReconciliationContext, year: int | None = None
) -> tuple[int, int] | None:
    """(year, month) of the newest household spending row, within `year` when
    given, or None. Transfer rows are excluded so a card payment cannot point
    at an empty month."""
    latest = await uow.transactions.get_latest_household_transaction_date(
        excluding_categories=ctx.non_spending_categories, year=year
    )
    return (latest.year, latest.month) if latest else None


async def resolve_period(
    uow: UnitOfWorkProtocol,
    ctx: ReconciliationContext,
    year: int | None,
    month: int | None,
) -> tuple[int, int]:
    """The (year, month) a spending page reports on. An explicit month always
    wins; otherwise the page opens on the latest month with household
    spending — within the named year, or the newest month overall when no
    year is named — and on the current calendar month when there is none.
    Household-anchored on purpose: Settle Up and Transactions reach the same
    anchor through `fetch_latest_spending_month`, so every page opens on the
    same month."""
    if year is not None and month is not None:
        return year, month
    now = datetime.now(UTC)
    anchor = await fetch_latest_spending_month(uow, ctx, year) or (
        year or now.year,
        now.month,
    )
    return anchor[0], month or anchor[1]


async def fetch_listed_rows(
    uow: UnitOfWorkProtocol,
    window: DateWindow,
    *,
    tags: tuple[str, ...] | None = None,
) -> list[Transaction]:
    """Every row in a window, transfers included. For the All list — takes
    no context so it cannot be "fixed" by accident."""
    start, end = window
    return await uow.transactions.get_by_date_range(start, end, tags=tags)


async def fetch_payer_rows(
    uow: UnitOfWorkProtocol, window: DateWindow
) -> list[Transaction]:
    """Every row with a payer in a window, transfers included. For
    settlement-candidate search: Venmo legs live in the Transfer group, and
    a joint account's row is never a leg."""
    start, end = window
    return await uow.transactions.get_by_date_range(start, end, payer_only=True)


async def fetch_account_rows(
    uow: UnitOfWorkProtocol, account_ids: list[UUID]
) -> list[Transaction]:
    """Every row in the given accounts, at any date, transfers included. For
    moving rows between accounts, which needs all of them."""
    return await uow.transactions.get_by_account_ids(account_ids)


async def fetch_joint_rows(
    uow: UnitOfWorkProtocol, joint_account_ids: list[UUID], limit: int
) -> list[Transaction]:
    """The joint accounts' newest `limit` rows, newest first. Transfers stay:
    the House activity list shows them as such."""
    return await uow.transactions.get_recent_by_account_ids(joint_account_ids, limit)


@define(frozen=True, slots=True)
class TransactionShares:
    """One row's split: each person's percentage and unsigned amount.

    Empty when the row has none: a transfer- or income-kind row (unless it
    is a joint deposit, which is its depositor's), or a row whose payer or
    owners are not the couple.
    """

    percentages: Mapping[UUID, int]
    amounts: Mapping[UUID, Decimal]


NO_SHARES = TransactionShares(percentages={}, amounts={})


def row_shares(tx: Transaction, ctx: ReconciliationContext) -> TransactionShares:
    """The row's split, or NO_SHARES. A row whose payer or owners are not
    the couple (stale data) logs a warning instead of failing the read."""
    kind = ctx.category_kinds.get(tx.category)
    if kind is not None and not is_spending_kind(kind) and depositor_of(tx) is None:
        return NO_SHARES
    person_ids = ctx.person_ids
    try:
        return TransactionShares(
            percentages=owner_shares(tx, person_ids),
            amounts=share_amounts(tx, person_ids),
        )
    except InvariantViolationError as e:
        logger.warning(
            "transaction_shares_unresolved", transaction_id=str(tx.id), error=str(e)
        )
        return NO_SHARES


def with_shares(
    rows: Iterable[Transaction], ctx: ReconciliationContext
) -> dict[UUID, TransactionShares]:
    """Each row's split, by row id."""
    return {tx.id: row_shares(tx, ctx) for tx in rows}
