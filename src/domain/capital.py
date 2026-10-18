"""Each owner's capital in the home they own together, from tagged rows.

A row tagged `share:<kind>` is a contribution of that kind. When the
asset's settings count the kind, each owner is credited with their share of
the row's amount (`share_amounts`): money out adds to the credit, and money
in (a refund) takes it off, by the signed-amount convention. Whether refunds
reduce credits is still the owners' call, so this rule is reversible. A
repair counts only when its amount reaches the repair threshold.
`share:none`, an unknown kind, and an untagged row credit nothing.

The tag is the only lever: a credit ignores `is_excluded`, `is_settlement`,
`household`, and the category's kind (a closing wire is often a transfer),
and a row from any account counts. A personal row the payer keeps in full
(`s100` or `household`) credits the payer in full.

An owner's capital is the sum of their credits; their share is their
capital divided by both. Like settlement balances, these figures are
computed from the rows on each read and never stored.
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.constants import SHARE_TAG_PREFIX
from src.domain.entities.co_owned_asset import (
    CONTRIBUTION_KINDS,
    ContributionKind,
    CoOwnedAsset,
)
from src.domain.entities.transaction import Transaction
from src.domain.house import OwnerAmount, ShareHistoryPoint, share_percentages
from src.domain.month_key import MonthKey, months_through
from src.domain.splits import share_amounts
from src.domain.tags import tag_value

type _Credit = tuple[MonthKey, ContributionKind, dict[UUID, Decimal]]


@define(frozen=True, slots=True)
class CapitalAccounts:
    """Each owner's capital, by contribution kind and month by month.

    ``by_kind`` holds only the kinds with a counted row, in
    ``CONTRIBUTION_KINDS`` order. ``history`` has one point per month, from
    the first credit's month through the given month. Across the kinds, each
    owner's amounts sum to their capital in the last point.
    """

    by_kind: Mapping[ContributionKind, tuple[OwnerAmount, ...]]
    history: tuple[ShareHistoryPoint, ...]


def share_kind(tx: Transaction) -> ContributionKind | None:
    """The contribution kind the row's first `share:` tag names, or None when
    the row has no such tag or the tag names no kind (`share:none`)."""
    value = tag_value(tx.tags, SHARE_TAG_PREFIX)
    return value if value in CONTRIBUTION_KINDS else None


def _counted_kind(tx: Transaction, asset: CoOwnedAsset) -> ContributionKind | None:
    """The row's contribution kind when it counts toward the shares, else None.

    A kind counts when the asset lists it; a repair counts only when its
    absolute amount is at least the repair threshold.
    """
    kind = share_kind(tx)
    if kind is None or kind not in asset.qualifying_kinds:
        return None
    if kind == "repair" and abs(tx.amount) < asset.repair_threshold:
        return None
    return kind


def _credits(
    rows: Iterable[Transaction], person_ids: Sequence[UUID], asset: CoOwnedAsset
) -> Iterator[_Credit]:
    """The month, kind, and each owner's credit of each counted row.

    The credits are the owners' shares of |amount| (`share_amounts`),
    positive for money out and negative for a refund, so they sum to
    -amount exactly. Raise InvariantViolationError as `share_amounts` does.
    """
    for tx in rows:
        kind = _counted_kind(tx, asset)
        if kind is None:
            continue
        sign = -1 if tx.amount > 0 else 1
        shares = share_amounts(tx, person_ids)
        yield (
            (tx.date.year, tx.date.month),
            kind,
            {person: sign * shares[person] for person in person_ids},
        )


def _history(
    by_month: Mapping[MonthKey, Mapping[UUID, Decimal]],
    person_ids: Sequence[UUID],
    through: MonthKey,
) -> tuple[ShareHistoryPoint, ...]:
    """Each owner's capital and percent at the end of each month, from the
    first credited month (or `through`, when none is earlier) through
    `through`. The percents round as `share_percentages` does."""
    running = dict.fromkeys(person_ids, Decimal(0))
    points: list[ShareHistoryPoint] = []
    for year, month in months_through(min([*by_month, through]), through):
        for person, credit in by_month.get((year, month), {}).items():
            running[person] += credit
        points.append(ShareHistoryPoint(year, month, share_percentages(running)))
    return tuple(points)


def capital_accounts(
    rows: Iterable[Transaction],
    person_ids: Sequence[UUID],
    asset: CoOwnedAsset,
    through: MonthKey,
) -> CapitalAccounts:
    """Each owner's capital from the rows dated through `through`.

    One pass over the rows; a row dated after `through` counts nowhere. The
    owners follow `person_ids` order.
    """
    by_kind: dict[ContributionKind, dict[UUID, Decimal]] = {}
    by_month: dict[MonthKey, dict[UUID, Decimal]] = {}
    for month, kind, credits in _credits(rows, person_ids, asset):
        if month > through:
            continue
        for totals in (
            by_kind.setdefault(kind, dict.fromkeys(person_ids, Decimal(0))),
            by_month.setdefault(month, dict.fromkeys(person_ids, Decimal(0))),
        ):
            for person, credit in credits.items():
                totals[person] += credit
    return CapitalAccounts(
        by_kind={
            kind: tuple(OwnerAmount(p, by_kind[kind][p]) for p in person_ids)
            for kind in CONTRIBUTION_KINDS
            if kind in by_kind
        },
        history=_history(by_month, person_ids, through),
    )
