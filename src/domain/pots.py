"""Pots and owner funds of the joint accounts, computed from their rows.

The money in the joint accounts is tracked by pot: a joint row's `pot:` tag
names its pot, and a row without one is in the unassigned pot. A pot-to-pot
transfer is two rows, each tagged with its own pot, so it moves money
between pots and leaves their sum unchanged.

Each deposit is its depositor's money: their own, or a gift to them, by its
`source:` tag. Each owner's unspent balance is what they deposited less
their share of the payments. An excluded row counts nowhere: in no pot and
in no owner's funds. Like settlement balances, these figures are computed
from the rows on each read and never stored.
"""

from collections.abc import Iterable, Iterator, Sequence, Set
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.constants import (
    POT_TAG_PREFIX,
    SOURCE_GIFT,
    SOURCE_TAG_PREFIX,
    UNASSIGNED_POT,
)
from src.domain.entities.transaction import Transaction
from src.domain.filters import (
    depositor_of,
    in_spending_category,
    is_reconciliation_relevant,
)
from src.domain.splits import share_amounts
from src.domain.tags import tag_value


@define(frozen=True, slots=True)
class PotBalance:
    """One pot: the money into it, the money out of it, and what is left."""

    name: str
    deposits: Decimal  # the sum of the positive amounts
    payments: Decimal  # the sum of the absolute negative amounts

    @property
    def balance(self) -> Decimal:
        """The sum of the pot's signed amounts."""
        return self.deposits - self.payments

    @property
    def is_unassigned(self) -> bool:
        """True for the pot of the rows that carry no pot tag."""
        return self.name == UNASSIGNED_POT


@define(frozen=True, slots=True)
class OwnerFunds:
    """What one owner put into the joint accounts and what of it is left.

    ``share_of_payments`` is the owner's share of the spending paid from the
    joint accounts, less their share of its refunds.
    """

    person_id: UUID
    own_deposits: Decimal
    gift_deposits: Decimal
    share_of_payments: Decimal

    @property
    def deposits(self) -> Decimal:
        return self.own_deposits + self.gift_deposits

    @property
    def unspent(self) -> Decimal:
        return self.deposits - self.share_of_payments


def _counted(rows: Iterable[Transaction]) -> Iterator[Transaction]:
    """The rows that count toward pots and owner funds: all but the excluded."""
    return (tx for tx in rows if not tx.is_excluded)


def _pot_of(tx: Transaction) -> str:
    """The row's pot: the value of its `pot:` tag, else the unassigned pot."""
    return tag_value(tx.tags, POT_TAG_PREFIX) or UNASSIGNED_POT


def compute_pot_balances(joint_rows: Iterable[Transaction]) -> tuple[PotBalance, ...]:
    """Each pot's balance over the joint rows, transfers included.

    Excluded rows count in no pot. The pots are sorted by name, with the
    unassigned pot last. The balances sum to the sum of the signed amounts
    of the rows that count.
    """
    deposits: dict[str, Decimal] = {}
    payments: dict[str, Decimal] = {}
    for tx in _counted(joint_rows):
        pot = _pot_of(tx)
        deposits[pot] = deposits.get(pot, Decimal(0)) + max(tx.amount, Decimal(0))
        payments[pot] = payments.get(pot, Decimal(0)) + max(-tx.amount, Decimal(0))
    names = sorted(deposits, key=lambda name: (name == UNASSIGNED_POT, name))
    return tuple(PotBalance(name, deposits[name], payments[name]) for name in names)


def compute_owner_funds(
    joint_rows: Iterable[Transaction],
    person_ids: Sequence[UUID],
    non_spending_categories: Set[str],
) -> tuple[OwnerFunds, ...]:
    """Each owner's deposits, share of payments, and unspent balance.

    A deposit (money in that names its depositor) is the depositor's alone:
    a gift when tagged `source:gift`, else their own money. A spending row
    (reconciliation-relevant, in a spending category) splits by its owner
    shares (`share_amounts`): a payment adds each owner's share, and money
    in with no depositor is a refund that takes each owner's share off.
    Other rows (transfer- or income-kind rows with no depositor, settlement
    rows) and excluded rows change no owner's funds. The result holds one
    entry for each owner, in the order of `person_ids`. Raise
    InvariantViolationError as `share_amounts` does.
    """
    zero = dict.fromkeys(person_ids, Decimal(0))
    own, gifts, spent = dict(zero), dict(zero), dict(zero)
    for tx in _counted(joint_rows):
        if depositor_of(tx) is not None:
            gift = tag_value(tx.tags, SOURCE_TAG_PREFIX) == SOURCE_GIFT
            deposited = gifts if gift else own
            for person, amount in share_amounts(tx, person_ids).items():
                deposited[person] += amount
        elif is_reconciliation_relevant(tx) and in_spending_category(
            tx, non_spending_categories
        ):
            sign = 1 if tx.amount < 0 else -1
            for person, amount in share_amounts(tx, person_ids).items():
                spent[person] += sign * amount
    return tuple(
        OwnerFunds(
            person_id=person,
            own_deposits=own[person],
            gift_deposits=gifts[person],
            share_of_payments=spent[person],
        )
        for person in person_ids
    )
