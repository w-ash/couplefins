from typing import Literal, cast, get_args
from uuid import UUID

from attrs import define

# What a group's rows mean for the money math. An `expense` group is spending.
# A `transfer` group is money movement between the couple's own accounts
# (credit card payments, account transfers): its rows never count toward
# spending, budgets, or settlement, but stay visible on the Transactions page.
GroupKind = Literal["expense", "transfer"]


def parse_group_kind(raw: str) -> GroupKind:
    """Narrow a stored string to GroupKind at the persistence boundary."""
    if raw in get_args(GroupKind):
        return cast(GroupKind, raw)
    raise ValueError(f"Unknown category group kind: {raw!r}")


@define(frozen=True, slots=True)
class CategoryGroup:
    id: UUID
    name: str
    icon: str | None = None
    kind: GroupKind = "expense"
