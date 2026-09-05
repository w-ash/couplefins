"""Share primitives: one person's part of a transaction.

The lenses that decide which rows count for whom live in `spending_lens`.
"""

from decimal import Decimal
from uuid import UUID

from src.domain.entities.transaction import Transaction
from src.domain.splits import compute_shares


def compute_person_share(tx: Transaction, person_id: UUID) -> Decimal:
    """One person's share of a transaction (unsigned magnitude)."""
    payer_share, other_share = compute_shares(tx.amount, tx.payer_percentage)
    return payer_share if tx.payer_person_id == person_id else other_share


def signed_person_share(tx: Transaction, person_id: UUID) -> Decimal:
    """One person's share with spend sign: an expense adds, a refund subtracts."""
    magnitude = compute_person_share(tx, person_id)
    return magnitude if tx.amount < 0 else -magnitude
