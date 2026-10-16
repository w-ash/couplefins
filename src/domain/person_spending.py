"""Share primitives: one person's part of a transaction.

The split itself lives in `splits`; the lenses that decide which rows count
for whom live in `spending_lens`.
"""

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from src.domain.entities.transaction import Transaction
from src.domain.splits import person_share


def signed_person_share(
    tx: Transaction, person_id: UUID, *, person_ids: Sequence[UUID]
) -> Decimal:
    """One person's share with spend sign: an expense adds, a refund subtracts."""
    magnitude = person_share(tx, person_id, person_ids)
    return magnitude if tx.amount < 0 else -magnitude
