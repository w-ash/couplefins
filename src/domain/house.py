"""House figures — every number the House page shows (v1.15.1).

The records, and the pure functions that derive their totals, percents, and
differences. The page renders the records and derives nothing. Money is
signed where a field says so, else a plain amount. Owner lists hold one entry
per owner, in the order of ``HouseFigures.persons``.
"""

from collections.abc import Mapping, Sequence
import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from attrs import define, evolve

from src.domain.entities.co_owned_asset import ContributionKind
from src.domain.pots import OwnerFunds

_TENTH = Decimal("0.1")

# ``ContributionKind`` values are the ``share:`` tag values and use hyphens;
# the kinds below are API enums and use snake_case.
type LoanKind = Literal["interest_only", "amortizing"]
type ObligationKind = Literal["loan_payment", "property_tax", "insurance", "other"]
type ActivityKind = Literal["deposit", "payment", "refund", "transfer"]


@define(frozen=True, slots=True)
class HousePerson:
    id: UUID
    name: str


@define(frozen=True, slots=True)
class OwnerAmount:
    """One owner's part of an amount."""

    person_id: UUID
    amount: Decimal


@define(frozen=True, slots=True)
class OwnerShare:
    """One owner's capital account and their percent (0-100) of all capital."""

    person_id: UUID
    capital: Decimal
    percent: Decimal


@define(frozen=True, slots=True)
class PutInKind:
    """What each owner put in of one contribution kind."""

    kind: ContributionKind
    amounts: tuple[OwnerAmount, ...]
    total: Decimal


@define(frozen=True, slots=True)
class PutInSection:
    kinds: tuple[PutInKind, ...]
    totals: tuple[OwnerAmount, ...]  # per owner, across all kinds
    total: Decimal
    unspent_deposits: tuple[OwnerAmount, ...]


@define(frozen=True, slots=True)
class ShareHistoryPoint:
    """The shares at the end of one month."""

    year: int
    month: int
    owners: tuple[OwnerShare, ...]


@define(frozen=True, slots=True)
class SharesSection:
    now: tuple[OwnerShare, ...]
    total_capital: Decimal
    history: tuple[ShareHistoryPoint, ...]  # ascending; the last point equals now


@define(frozen=True, slots=True)
class LoanFigures:
    id: UUID
    name: str
    kind: LoanKind
    balance: Decimal
    rate_percent: Decimal
    payment: Decimal
    next_due: datetime.date
    owner_parts: tuple[OwnerAmount, ...]  # sum to payment


@define(frozen=True, slots=True)
class ObligationFigures:
    """One upcoming payment and the bucket that pays it.

    ``shortfall`` is set when the balance that the bucket has left, after the
    earlier payments from it, cannot cover the payment.
    """

    id: UUID
    name: str
    kind: ObligationKind
    amount: Decimal
    is_estimate: bool
    due: datetime.date
    late_after: datetime.date | None
    pays_from: str | None
    shortfall: Decimal | None


@define(frozen=True, slots=True)
class Bucket:
    """Money set aside for one purpose, beside the bank's last balance.

    ``difference`` is ``bank_balance - balance``; all three bank fields are
    None when no bank balance is known for the bucket. ``is_unassigned``
    marks the bucket of the money that no pot names.
    """

    name: str
    balance: Decimal
    bank_balance: Decimal | None
    bank_balance_as_of: datetime.date | None
    difference: Decimal | None
    is_unassigned: bool


@define(frozen=True, slots=True)
class OwnerDeposits:
    """One owner's deposits into the joint accounts and what of them is left.

    ``unspent`` is ``own_deposits + gift_deposits - share_of_payments``
    (``OwnerFunds.unspent``).
    """

    person_id: UUID
    own_deposits: Decimal
    gift_deposits: Decimal
    share_of_payments: Decimal
    unspent: Decimal


@define(frozen=True, slots=True)
class SetAsideSection:
    """The buckets, their total beside the bank's last balance, and each
    owner's deposits.

    ``difference`` is ``bank_balance - total``; all three bank fields are
    None until the owners enter a bank balance.
    """

    buckets: tuple[Bucket, ...]
    total: Decimal
    bank_balance: Decimal | None
    bank_balance_as_of: datetime.date | None
    difference: Decimal | None
    owners: tuple[OwnerDeposits, ...]


@define(frozen=True, slots=True)
class ActivityRow:
    """One movement in a house account.

    ``amount`` is signed (negative = money out); ``shares`` sum to its
    absolute value. ``person_id`` names the depositor of a deposit.
    """

    id: UUID
    date: datetime.date
    account_name: str
    person_id: UUID | None
    kind: ActivityKind
    budget_line: str | None
    amount: Decimal
    shares: tuple[OwnerAmount, ...]


@define(frozen=True, slots=True)
class HouseFigures:
    as_of: datetime.date
    persons: tuple[HousePerson, ...]
    put_in: PutInSection
    shares: SharesSection
    loans: tuple[LoanFigures, ...]
    upcoming: tuple[ObligationFigures, ...]  # ascending by due
    set_aside: SetAsideSection
    recent_activity: tuple[ActivityRow, ...]  # newest first


def put_in_section(
    owner_ids: Sequence[UUID],
    kinds: Mapping[ContributionKind, tuple[OwnerAmount, ...]],
    unspent_deposits: tuple[OwnerAmount, ...],
) -> PutInSection:
    """Total each kind, each owner across all kinds, and all owners.

    The totals hold one entry for each owner, in the order of ``owner_ids``.
    An owner with no contribution gets a total of zero.
    """
    owner_totals = dict.fromkeys(owner_ids, Decimal(0))
    for amounts in kinds.values():
        for part in amounts:
            owner_totals[part.person_id] += part.amount
    totals = tuple(OwnerAmount(owner, owner_totals[owner]) for owner in owner_ids)
    return PutInSection(
        kinds=tuple(
            PutInKind(kind, amounts, sum((a.amount for a in amounts), Decimal(0)))
            for kind, amounts in kinds.items()
        ),
        totals=totals,
        total=sum((t.amount for t in totals), Decimal(0)),
        unspent_deposits=unspent_deposits,
    )


def share_percentages(capitals: Mapping[UUID, Decimal]) -> tuple[OwnerShare, ...]:
    """Give each owner's percent of all capital, in the order of ``capitals``.

    Percents round half up to 0.1. The last owner gets the remainder, so the
    percents sum to 100. When the capital total is zero, each percent is zero.
    """
    total = sum(capitals.values(), Decimal(0))
    if not total:
        return tuple(
            OwnerShare(owner, capital, Decimal(0))
            for owner, capital in capitals.items()
        )
    *firsts, (last_owner, last_capital) = capitals.items()
    shares = tuple(
        OwnerShare(
            owner,
            capital,
            (capital * 100 / total).quantize(_TENTH, rounding=ROUND_HALF_UP),
        )
        for owner, capital in firsts
    )
    remainder = 100 - sum((s.percent for s in shares), Decimal(0))
    return (*shares, OwnerShare(last_owner, last_capital, remainder))


def shares_section(history: tuple[ShareHistoryPoint, ...]) -> SharesSection:
    """Make the shares now from the last point of an ascending history."""
    now = history[-1].owners if history else ()
    return SharesSection(
        now=now,
        total_capital=sum((s.capital for s in now), Decimal(0)),
        history=history,
    )


def bucket(
    name: str,
    balance: Decimal,
    bank_balance: Decimal | None = None,
    bank_balance_as_of: datetime.date | None = None,
    *,
    is_unassigned: bool = False,
) -> Bucket:
    """Make a bucket and its difference from the bank balance, if one is known."""
    return Bucket(
        name=name,
        balance=balance,
        bank_balance=bank_balance,
        bank_balance_as_of=bank_balance_as_of,
        difference=None if bank_balance is None else bank_balance - balance,
        is_unassigned=is_unassigned,
    )


def owner_deposits(funds: OwnerFunds) -> OwnerDeposits:
    """Make the figures of one owner's funds, their unspent balance included."""
    return OwnerDeposits(
        person_id=funds.person_id,
        own_deposits=funds.own_deposits,
        gift_deposits=funds.gift_deposits,
        share_of_payments=funds.share_of_payments,
        unspent=funds.unspent,
    )


def set_aside_section(
    buckets: tuple[Bucket, ...],
    owners: tuple[OwnerDeposits, ...],
    bank_balance: Decimal | None = None,
    bank_balance_as_of: datetime.date | None = None,
) -> SetAsideSection:
    """Total the balances of the buckets, and the total's difference from
    the bank balance, if one is known."""
    total = sum((b.balance for b in buckets), Decimal(0))
    return SetAsideSection(
        buckets=buckets,
        total=total,
        bank_balance=bank_balance,
        bank_balance_as_of=bank_balance_as_of,
        difference=None if bank_balance is None else bank_balance - total,
        owners=owners,
    )


def with_shortfalls(
    upcoming: Sequence[ObligationFigures], balances: Mapping[str, Decimal]
) -> tuple[ObligationFigures, ...]:
    """Set the shortfall of each obligation from what its bucket has left.

    ``upcoming`` must be in due order, and ``balances`` maps each bucket name
    to its balance. Each payment takes from the balance that the earlier
    payments from the same bucket leave, and that balance does not go below
    zero. The shortfall is the part of the amount that the balance cannot
    cover. An obligation with no bucket, or with a bucket not in
    ``balances``, gets no shortfall.
    """
    left = dict(balances)
    result: list[ObligationFigures] = []
    for obligation in upcoming:
        bucket_name = obligation.pays_from
        if bucket_name is None or bucket_name not in left:
            result.append(evolve(obligation, shortfall=None))
            continue
        balance, amount = left[bucket_name], obligation.amount
        left[bucket_name] = max(balance - amount, Decimal(0))
        shortfall = amount - balance if balance < amount else None
        result.append(evolve(obligation, shortfall=shortfall))
    return tuple(result)
