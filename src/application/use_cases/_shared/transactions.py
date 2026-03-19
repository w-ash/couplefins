from uuid import UUID

from src.domain.dedup import ClassifiedTransaction, classify_transactions
from src.domain.entities.category import Category
from src.domain.entities.transaction import Transaction
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


async def get_other_person_names(
    uow: UnitOfWorkProtocol, person_id: UUID
) -> frozenset[str]:
    """Lowercased names of all persons except the given one (for spotted detection)."""
    return frozenset(
        p.name.lower() for p in await uow.persons.get_all() if p.id != person_id
    )


def find_new_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories with no row in the categories table at all."""
    known = {c.name for c in categories}
    return sorted(tx_categories - known)


def find_unmapped_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories that exist in DB but have group_id=None."""
    unmapped = {c.name for c in categories if c.group_id is None}
    return sorted(tx_categories & unmapped)


def find_all_unmapped_categories(
    categories: list[Category], tx_categories: set[str]
) -> list[str]:
    """Categories that are either unknown or known-but-unmapped (group_id=None).

    Single pass over categories to avoid redundant iteration.
    """
    known: set[str] = set()
    mapped: set[str] = set()
    for c in categories:
        known.add(c.name)
        if c.group_id is not None:
            mapped.add(c.name)
    return sorted(tx_categories - mapped)


async def get_latest_transaction_month(
    uow: UnitOfWorkProtocol,
) -> tuple[int, int] | None:
    """Returns (year, month) of the most recent shared transaction, or None."""
    latest_date = await uow.transactions.get_latest_household_transaction_date()
    return (latest_date.year, latest_date.month) if latest_date else None


async def classify_against_existing(
    incoming: list[Transaction], person_id: UUID, uow: UnitOfWorkProtocol
) -> tuple[list[ClassifiedTransaction], list[Transaction]]:
    """Fetch existing transactions for the incoming date range and classify.

    Returns (classified, existing) — existing is needed by preview to show diffs.
    """
    if not incoming:
        return [], []
    dates = [tx.date for tx in incoming]
    existing = await uow.transactions.get_by_person_and_date_range(
        person_id, min(dates), max(dates)
    )
    return classify_transactions(incoming, existing), existing
