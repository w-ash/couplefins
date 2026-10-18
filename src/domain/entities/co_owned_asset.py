from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, get_args
from uuid import UUID

from attrs import define

# What a qualifying contribution paid for. The values are the `share:` tag
# values, so they use hyphens. The named alias keeps its name in the API
# schema; the plain one gives the values at runtime.
_ContributionValues = Literal[
    "closing",
    "loan-interest",
    "loan-principal",
    "property-tax",
    "insurance",
    "repair",
    "agreed-work",
]
type ContributionKind = _ContributionValues
CONTRIBUTION_KINDS: tuple[ContributionKind, ...] = get_args(_ContributionValues)


def ordered_kinds(kinds: Iterable[ContributionKind]) -> list[ContributionKind]:
    """Return `kinds` in `CONTRIBUTION_KINDS` order, each once."""
    chosen = set(kinds)
    return [kind for kind in CONTRIBUTION_KINDS if kind in chosen]


@define(frozen=True, slots=True)
class CoOwnedAsset:
    """The home the couple owns together, and the settings of its shares.

    A row's contribution counts toward the owners' shares when its kind is
    in ``qualifying_kinds``; a repair counts only when its amount reaches
    ``repair_threshold``. ``bank_balance`` is the joint accounts' balance
    last read from the bank, on ``bank_balance_as_of``.
    """

    id: UUID
    name: str
    repair_threshold: Decimal
    qualifying_kinds: frozenset[ContributionKind]
    bank_balance: Decimal | None
    bank_balance_as_of: date | None
    created_at: datetime

    def __attrs_post_init__(self) -> None:
        if self.repair_threshold < 0:
            raise ValueError(
                f"repair_threshold must not be negative, got {self.repair_threshold}"
            )
