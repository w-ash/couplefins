"""Shared exclusion predicates for reconciliation and budget math.

Single source of truth for "does this transaction count toward
spending/settlement?" — replaces hand-copied `is_excluded or is_settlement`
checks scattered across the domain and application layers.
"""

from collections.abc import Set
from uuid import UUID

from src.domain.constants import SplitDefaults
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.split_rules import is_joint_payer


def is_joint_row(tx: Transaction) -> bool:
    """True when a row belongs to a joint account and has no payer.

    With `payer_of` and `split_rules.is_joint_payer`, the only places a
    missing payer is tested — a grep-gate test enforces it.
    """
    return is_joint_payer(tx.payer_person_id)


def payer_of(tx: Transaction) -> UUID:
    """The payer of a personal row. Raise InvariantViolationError on a joint row."""
    if tx.payer_person_id is None:
        raise InvariantViolationError(f"Transaction {tx.id} is joint and has no payer")
    return tx.payer_person_id


def depositor_of(tx: Transaction) -> UUID | None:
    """Whose deposit a joint row is: its depositor when the row is money in
    (amount > 0), else None. A deposit is its depositor's money alone."""
    if is_joint_row(tx) and tx.amount > 0:
        return tx.depositor_person_id
    return None


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

    Reconciliation-relevant, actually split (payer_percentage == 100 means
    the payer absorbs the whole bill and nothing is owed back), and not
    joint: a joint account's row was paid by both owners' money, so neither
    owes the other for it.
    """
    return (
        is_reconciliation_relevant(tx)
        and tx.payer_percentage < SplitDefaults.MAX_PAYER_PERCENTAGE
        and not is_joint_row(tx)
    )


def in_spending_category(tx: Transaction, non_spending_categories: Set[str]) -> bool:
    """True when the row's category is in no transfer- or income-kind group.

    `non_spending_categories` names the categories of those groups.
    """
    return tx.category not in non_spending_categories


def exclude_non_spending(
    transactions: list[Transaction], non_spending_categories: Set[str]
) -> list[Transaction]:
    """Drop rows in transfer-kind categories (credit card payments, account
    transfers) and income-kind categories (paychecks, dividends). Neither is
    spending: the purchases a card payment covers were already counted when
    they hit the card, and a paycheck is money in. Category-scoped complement
    to `is_reconciliation_relevant`, with the same reach — spending, budgets,
    and settlement. Applied once, in the application's transaction reads
    module — the only place use cases read transaction lists — so every
    computation downstream sees the same rows.
    """
    if not non_spending_categories:
        return transactions
    return [
        tx for tx in transactions if in_spending_category(tx, non_spending_categories)
    ]
