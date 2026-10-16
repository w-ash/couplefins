"""Per-row splits: each owner's percentage and amount of one transaction.

A personal row splits between its payer (`payer_percentage`) and the partner
(the rest). A joint row has no payer: a deposit that names its depositor is
the depositor's alone; any other joint row splits between the two owners by
its `owner_shares` override, or 50/50 when it has none. Every share of a row
comes from `_lead_share`; nothing else computes one.

The functions are category-blind. Transfer- and income-kind rows are removed
upstream by `exclude_non_spending`.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from src.domain.constants import CoupleDefaults, SplitDefaults
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.filters import depositor_of, is_joint_row, payer_of

_QUANTIZE_EXP = Decimal("0.01")
_HUNDRED = Decimal(100)


def compute_shares(amount: Decimal, payer_percentage: int) -> tuple[Decimal, Decimal]:
    """Return (payer_share, other_share) for a transaction amount and split."""
    abs_amount = abs(amount)
    payer_pct = Decimal(payer_percentage)
    payer_share = (abs_amount * payer_pct / _HUNDRED).quantize(
        _QUANTIZE_EXP, rounding=ROUND_HALF_UP
    )
    other_share = abs_amount - payer_share
    return payer_share, other_share


def _couple(person_ids: Sequence[UUID]) -> tuple[UUID, UUID]:
    if len(person_ids) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        raise InvariantViolationError(
            f"A split needs {CoupleDefaults.EXPECTED_PERSON_COUNT} persons, "
            f"got {len(person_ids)}"
        )
    first, second = person_ids
    return first, second


def _require_member(
    tx: Transaction, person_id: UUID, couple: tuple[UUID, UUID]
) -> None:
    if person_id not in couple:
        raise InvariantViolationError(
            f"Transaction {tx.id} names {person_id}, who is not one of the couple"
        )


def _lead_share(tx: Transaction, person_ids: Sequence[UUID]) -> tuple[UUID, UUID, int]:
    """Return (lead, other, lead's percentage) of a row.

    The lead is the payer of a personal row and the first of `person_ids`
    for a joint row; the lead's amount rounds half-up. Raise
    InvariantViolationError unless `person_ids` names exactly two persons
    and the row's payer, depositor, or override owners are those two.
    """
    couple = _couple(person_ids)
    first, second = couple
    if is_joint_row(tx):
        depositor = depositor_of(tx)
        if depositor is not None:
            _require_member(tx, depositor, couple)
            full = SplitDefaults.MAX_PAYER_PERCENTAGE
            return first, second, full if depositor == first else 0
        if tx.owner_shares is None:
            return first, second, SplitDefaults.DEFAULT_PAYER_PERCENTAGE
        if set(tx.owner_shares) != set(couple):
            raise InvariantViolationError(
                f"Transaction {tx.id} owner_shares name other persons than the couple"
            )
        return first, second, tx.owner_shares[first]
    payer = payer_of(tx)
    _require_member(tx, payer, couple)
    return payer, second if payer == first else first, tx.payer_percentage


def owner_shares(tx: Transaction, person_ids: Sequence[UUID]) -> dict[UUID, int]:
    """Return each owner's percentage of a row.

    A personal row gives `{payer: payer_percentage, partner: rest}`, payer
    first. A joint row gives, in `person_ids` order, 100/0 to the depositor
    of a deposit, else its `owner_shares` override, else 50/50. Raise
    InvariantViolationError as `_lead_share` does.
    """
    lead, other, pct = _lead_share(tx, person_ids)
    return {lead: pct, other: SplitDefaults.MAX_PAYER_PERCENTAGE - pct}


def share_amounts(tx: Transaction, person_ids: Sequence[UUID]) -> dict[UUID, Decimal]:
    """Return each owner's unsigned share of the row's amount.

    The first owner in `owner_shares` order gets the share rounded half-up;
    the other gets the remainder, so the two sum to |amount|.
    """
    lead, other, pct = _lead_share(tx, person_ids)
    lead_amount, other_amount = compute_shares(tx.amount, pct)
    return {lead: lead_amount, other: other_amount}


def person_share(
    tx: Transaction, person_id: UUID, person_ids: Sequence[UUID]
) -> Decimal:
    """Return one person's unsigned share of the row's amount: their entry
    in `share_amounts`, computed without building the split."""
    lead, other, pct = _lead_share(tx, person_ids)
    lead_amount, other_amount = compute_shares(tx.amount, pct)
    if person_id == lead:
        return lead_amount
    if person_id == other:
        return other_amount
    raise InvariantViolationError(f"Person {person_id} is not one of the couple")
