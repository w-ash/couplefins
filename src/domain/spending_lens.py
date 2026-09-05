"""One lens per way of looking at spending; one accumulator behind them.

Budget, Insights, and Dashboard all pass a lens into the same functions, so
"what counts as spending for whom" is defined exactly once:

- `HouseholdLens`: household rows at full amount (plus personal rows in
  `include_personal` categories, attributed to their payer).
- `PersonalLens`: one person's signed share; a row is theirs only when that
  share is nonzero, so a partner-paid `household, s100` row (their own
  concert ticket) is household-only.
- `SplitLens`: reconcile()'s settlement universe — split rows, household or
  not, at full amount. Not a page lens.
- `AllRowsLens`: the Dashboard's "all" scope — every reconciliation-relevant
  row, household or not, at full amount; personal rows attributed to their
  payer, so household + personal partitions the total exactly.

Every lens nets refunds (signed-amount convention): an expense adds, a
refund subtracts.
"""

from collections import defaultdict
from collections.abc import Iterable, Set
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from attrs import define

from src.domain.categories import (
    CategoryBreakdown,
    CategoryGroupBreakdown,
    group_category_breakdowns,
)
from src.domain.constants import UNCATEGORIZED_GROUP_NAME
from src.domain.entities.transaction import Transaction
from src.domain.filters import is_reconciliation_relevant, is_split_relevant
from src.domain.person_spending import compute_person_share, signed_person_share

# Where a row's money came from, as the spending-flow chart draws it. Full-
# amount lenses answer with the payer; a person's lens answers with the kind
# of claim they have on the row.
type FlowSourceKind = Literal["payer", "household_share", "personal", "spotted_for_me"]


@define(frozen=True, slots=True)
class FlowSource:
    kind: FlowSourceKind
    person_id: UUID


def _paid_by(tx: Transaction) -> FlowSource:
    return FlowSource("payer", tx.payer_person_id)


class SpendingLens(Protocol):
    def is_relevant(self, tx: Transaction, /) -> bool:
        """Does this row count under the lens?"""
        ...

    def contribution(self, tx: Transaction, /) -> Decimal:
        """Signed amount the row adds: expense positive, refund negative."""
        ...

    def personal_owner(self, tx: Transaction, /) -> UUID | None:
        """Whose personal spending a non-household row is; None = unattributed."""
        ...

    def flow_source(self, tx: Transaction, /) -> FlowSource:
        """Where the money came from, for the spending-flow chart."""
        ...


@define(frozen=True, slots=True)
class HouseholdLens:
    """Household rows at full amount. Categories in `personal_categories`
    (Budget's include_personal) also admit personal rows, attributed to
    their payer."""

    personal_categories: Set[str] = frozenset()

    def is_relevant(self, tx: Transaction) -> bool:
        return is_reconciliation_relevant(tx) and (
            tx.household or tx.category in self.personal_categories
        )

    @staticmethod
    def contribution(tx: Transaction) -> Decimal:
        return -tx.amount

    def personal_owner(self, tx: Transaction) -> UUID | None:
        return tx.payer_person_id if tx.category in self.personal_categories else None

    @staticmethod
    def flow_source(tx: Transaction) -> FlowSource:
        return _paid_by(tx)


@define(frozen=True, slots=True)
class PersonalLens:
    """One person's share. A row is theirs only when that share is nonzero:
    their share of household splits, their own personal rows, and what their
    partner spotted for them."""

    person_id: UUID

    def is_relevant(self, tx: Transaction) -> bool:
        return (
            is_reconciliation_relevant(tx)
            and compute_person_share(tx, self.person_id) != 0
        )

    def contribution(self, tx: Transaction) -> Decimal:
        return signed_person_share(tx, self.person_id)

    def personal_owner(self, _tx: Transaction, /) -> UUID | None:
        return self.person_id

    def flow_source(self, tx: Transaction) -> FlowSource:
        """A household row is my share of the couple's spending; a row I paid
        is personal; a row my partner paid that I owe part of is theirs to
        settle — "spotted for me" (a personal split lands here too)."""
        if tx.household:
            return FlowSource("household_share", tx.payer_person_id)
        if tx.payer_person_id == self.person_id:
            return FlowSource("personal", tx.payer_person_id)
        return FlowSource("spotted_for_me", tx.payer_person_id)


@define(frozen=True, slots=True)
class SplitLens:
    """reconcile()'s settlement universe: split rows, household or not."""

    @staticmethod
    def is_relevant(tx: Transaction) -> bool:
        return is_split_relevant(tx)

    @staticmethod
    def contribution(tx: Transaction) -> Decimal:
        return -tx.amount

    @staticmethod
    def personal_owner(_tx: Transaction, /) -> UUID | None:
        return None

    @staticmethod
    def flow_source(tx: Transaction) -> FlowSource:
        return _paid_by(tx)


@define(frozen=True, slots=True)
class AllRowsLens:
    """Every row that counts toward spending, at full amount. A personal
    row is its payer's, so `source_split` of an all-rows breakdown is a
    partition: household + personal == total."""

    @staticmethod
    def is_relevant(tx: Transaction) -> bool:
        return is_reconciliation_relevant(tx)

    @staticmethod
    def contribution(tx: Transaction) -> Decimal:
        return -tx.amount

    @staticmethod
    def personal_owner(tx: Transaction) -> UUID | None:
        return tx.payer_person_id

    @staticmethod
    def flow_source(tx: Transaction) -> FlowSource:
        return _paid_by(tx)


def select(lens: SpendingLens, txs: list[Transaction]) -> list[Transaction]:
    """Rows that count under the lens."""
    return [tx for tx in txs if lens.is_relevant(tx)]


def total_spending(lens: SpendingLens, txs: list[Transaction]) -> Decimal:
    """Net spending under the lens."""
    return sum((lens.contribution(tx) for tx in select(lens, txs)), Decimal(0))


def compute_breakdowns(
    lens: SpendingLens,
    txs: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
) -> list[CategoryGroupBreakdown]:
    """Per-category, rolled up per group, under the lens. The single
    accumulator: it selects rows itself so a caller cannot skip the predicate."""
    cat_total: dict[str, Decimal] = defaultdict(Decimal)
    cat_count: dict[str, int] = defaultdict(int)
    cat_household: dict[str, Decimal] = defaultdict(Decimal)
    cat_personal: dict[str, dict[UUID, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )

    for tx in select(lens, txs):
        amount = lens.contribution(tx)
        cat_total[tx.category] += amount
        cat_count[tx.category] += 1
        if tx.household:
            cat_household[tx.category] += amount
        else:
            owner = lens.personal_owner(tx)
            if owner is not None:
                cat_personal[tx.category][owner] += amount

    breakdowns = [
        CategoryBreakdown(
            category=cat,
            group_id=gid,
            group_name=gname,
            total_amount=amount,
            transaction_count=cat_count[cat],
            household_amount=cat_household.get(cat, Decimal(0)),
            personal_amounts=dict(cat_personal.get(cat, {})),
        )
        for cat, amount in cat_total.items()
        for gid, gname in [category_lookup.get(cat, (None, UNCATEGORIZED_GROUP_NAME))]
    ]
    return group_category_breakdowns(breakdowns)


def source_split(
    breakdowns: Iterable[CategoryGroupBreakdown],
) -> tuple[Decimal, Decimal]:
    """(household, personal) spending across the given group breakdowns."""
    household = Decimal(0)
    personal = Decimal(0)
    for gb in breakdowns:
        for cb in gb.categories:
            household += cb.household_amount
            personal += sum(cb.personal_amounts.values(), Decimal(0))
    return household, personal
