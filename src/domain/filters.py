"""Shared exclusion predicates for reconciliation and budget math.

Single source of truth for "does this transaction count toward
spending/settlement?" — replaces hand-copied `is_excluded or is_settlement`
checks scattered across the domain and application layers.
"""

from collections.abc import Set

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction import Transaction


def is_reconciliation_relevant(tx: Transaction) -> bool:
    """True when a transaction counts toward spending/settlement.

    A transaction is reconciliation-relevant when it is neither a linked
    settlement transfer nor manually excluded. Do not inline
    `is_settlement or is_excluded` (in any polarity) anywhere else — a
    grep-gate test enforces this.
    """
    return not tx.is_settlement and not tx.is_excluded


def is_split_relevant(tx: Transaction) -> bool:
    """True when a transaction participates in settlement math.

    Reconciliation-relevant and actually split — payer_percentage == 100
    means the payer absorbs the whole bill and nothing is owed back.
    """
    return (
        is_reconciliation_relevant(tx)
        and tx.payer_percentage < SplitDefaults.MAX_PAYER_PERCENTAGE
    )


def exclude_transfers(
    transactions: list[Transaction], transfer_categories: Set[str]
) -> list[Transaction]:
    """Drop rows in transfer-kind categories (credit card payments, account
    transfers). They are money movement, not spending: the purchases a card
    payment covers were already counted when they hit the card. Category-
    scoped complement to `is_reconciliation_relevant`, with the same reach —
    spending, budgets, and settlement. Applied once, in the application's
    transaction reads module — the only place use cases read transaction
    lists — so every computation downstream sees the same rows.
    """
    if not transfer_categories:
        return transactions
    return [tx for tx in transactions if tx.category not in transfer_categories]
