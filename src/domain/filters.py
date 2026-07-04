"""Shared exclusion predicate for reconciliation and budget math.

Single source of truth for "does this transaction count toward
spending/settlement?" — replaces hand-copied `is_excluded or is_settlement`
checks scattered across the domain and application layers.
"""

from src.domain.entities.transaction import Transaction


def is_reconciliation_relevant(tx: Transaction) -> bool:
    """True when a transaction counts toward spending/settlement.

    A transaction is reconciliation-relevant when it is neither a linked
    settlement transfer nor manually excluded. Do not inline
    `is_settlement or is_excluded` (in any polarity) anywhere else — a
    grep-gate test enforces this.
    """
    return not tx.is_settlement and not tx.is_excluded
