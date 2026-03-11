from uuid import UUID

from src.domain.dedup import ClassifiedTransaction, classify_transactions
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.transaction import Transaction
from src.domain.repositories.unit_of_work import UnitOfWorkProtocol


def find_new_categories(
    mappings: list[CategoryMapping], tx_categories: set[str]
) -> list[str]:
    """Categories with no row in category_mappings at all."""
    known = {m.category for m in mappings}
    return sorted(tx_categories - known)


def find_unmapped_categories(
    mappings: list[CategoryMapping], tx_categories: set[str]
) -> list[str]:
    """Categories that exist in DB but have group_id=None."""
    unmapped = {m.category for m in mappings if m.group_id is None}
    return sorted(tx_categories & unmapped)


def find_all_unmapped_categories(
    mappings: list[CategoryMapping], tx_categories: set[str]
) -> list[str]:
    """Categories that are either unknown or known-but-unmapped (group_id=None).

    Single pass over mappings to avoid redundant iteration.
    """
    known: set[str] = set()
    mapped: set[str] = set()
    for m in mappings:
        known.add(m.category)
        if m.group_id is not None:
            mapped.add(m.category)
    return sorted(tx_categories - mapped)


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
