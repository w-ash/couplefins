"""A row as a joint account's: the one transform behind importing a row on a
joint label and marking a label joint."""

from collections.abc import Sequence
from uuid import UUID

from attrs import evolve

from src.domain.constants import SplitDefaults
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.parsing.depositor import match_depositor
from src.domain.splits import owner_shares


def as_joint_row(
    tx: Transaction,
    *,
    account_id: UUID,
    persons: Sequence[Person],
    carry_split: bool,
) -> Transaction:
    """Return a personal row as the joint account's row.

    The row has no payer, is household, is unsplit, and is out of settlement.
    With `carry_split`, a hand-set split (payer_percentage < 100) becomes the
    owner shares: the old payer keeps their percentage, the partner takes
    the rest. Money in (amount > 0) names its depositor when exactly one of
    `persons` appears in its merchant, statement, or notes.
    """
    split = carry_split and tx.payer_percentage < SplitDefaults.MAX_PAYER_PERCENTAGE
    return evolve(
        tx,
        account_id=account_id,
        payer_person_id=None,
        payer_percentage=SplitDefaults.MAX_PAYER_PERCENTAGE,
        household=True,
        is_settlement=False,
        owner_shares=owner_shares(tx, [p.id for p in persons]) if split else None,
        depositor_person_id=(
            match_depositor((tx.merchant, tx.original_statement, tx.notes), persons)
            if tx.amount > 0
            else None
        ),
    )
