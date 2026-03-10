from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.transaction import Transaction


def find_unmapped_categories(
    mappings: list[CategoryMapping], tx_categories: set[str]
) -> list[str]:
    """Return sorted list of transaction categories that have no mapping."""
    mapped = {m.category for m in mappings}
    return sorted(tx_categories - mapped)


def count_shared(transactions: list[Transaction]) -> tuple[int, int]:
    """Return (shared_count, personal_count)."""
    shared = sum(1 for tx in transactions if tx.is_shared)
    return shared, len(transactions) - shared
