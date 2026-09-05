from typing import Literal, cast, get_args
from uuid import UUID

from attrs import define

# What a group's rows mean for the money math. An `expense` group is spending.
# A `transfer` group is money movement between the couple's own accounts
# (credit card payments, account transfers); an `income` group is money
# coming in (paychecks, dividends). Neither counts toward spending, budgets,
# or settlement, but both stay visible on the Transactions page.
GroupKind = Literal["expense", "transfer", "income"]


def is_spending_kind(kind: GroupKind) -> bool:
    """Only expense groups are spending; transfers and income are not."""
    return kind == "expense"


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
