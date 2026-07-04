from collections import defaultdict
from collections.abc import Set
from decimal import Decimal
from uuid import UUID

from attrs import Factory, define

from src.domain.constants import UNCATEGORIZED_GROUP_NAME
from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.transaction import Transaction


@define(frozen=True, slots=True)
class CategoryBreakdown:
    category: str
    group_id: UUID | None
    group_name: str
    total_amount: Decimal
    transaction_count: int
    household_amount: Decimal = Decimal(0)
    personal_amounts: dict[UUID, Decimal] = Factory(dict[UUID, Decimal])


@define(frozen=True, slots=True)
class CategoryGroupBreakdown:
    group_id: UUID | None
    group_name: str
    total_amount: Decimal
    transaction_count: int
    categories: list[CategoryBreakdown]


def build_category_lookup(
    categories: list[Category],
    category_groups: list[CategoryGroup],
) -> dict[str, tuple[UUID, str]]:
    group_names = {g.id: g.name for g in category_groups}
    return {
        c.name: (c.group_id, group_names.get(c.group_id, "Unknown"))
        for c in categories
        if c.group_id is not None
    }


def get_personal_included_categories(categories: list[Category]) -> set[str]:
    return {c.name for c in categories if c.include_personal}


def compute_category_breakdowns(
    transactions: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
    personal_categories: Set[str] = frozenset(),
) -> list[CategoryGroupBreakdown]:
    # Accumulate per category
    cat_amounts: dict[str, Decimal] = defaultdict(Decimal)
    cat_counts: dict[str, int] = defaultdict(int)
    cat_household: dict[str, Decimal] = defaultdict(Decimal)
    cat_personal: dict[str, dict[UUID, Decimal]] = defaultdict(
        lambda: defaultdict(Decimal)
    )

    for tx in transactions:
        # Signed contribution: an expense (amount < 0) adds to spend, a
        # refund (amount > 0) subtracts — mirrors reconcile()'s
        # total_spending - total_refunds. Never inflate spend with abs().
        spend = -tx.amount
        cat_amounts[tx.category] += spend
        cat_counts[tx.category] += 1

        if tx.household:
            cat_household[tx.category] += spend
        elif tx.category in personal_categories:
            cat_personal[tx.category][tx.payer_person_id] += spend

    # Build CategoryBreakdown per category
    category_breakdowns: list[CategoryBreakdown] = []
    for cat, amount in cat_amounts.items():
        gid, gname = category_lookup.get(cat, (None, UNCATEGORIZED_GROUP_NAME))
        category_breakdowns.append(
            CategoryBreakdown(
                category=cat,
                group_id=gid,
                group_name=gname,
                total_amount=amount,
                transaction_count=cat_counts[cat],
                household_amount=cat_household.get(cat, Decimal(0)),
                personal_amounts=dict(cat_personal.get(cat, {})),
            )
        )

    return group_category_breakdowns(category_breakdowns)


def group_category_breakdowns(
    category_breakdowns: list[CategoryBreakdown],
) -> list[CategoryGroupBreakdown]:
    """Roll up per-category breakdowns into per-group breakdowns, sorted by total."""
    groups: dict[UUID | None, list[CategoryBreakdown]] = {}
    for cb in category_breakdowns:
        groups.setdefault(cb.group_id, []).append(cb)

    result: list[CategoryGroupBreakdown] = []
    for gid, cats in groups.items():
        group_name = cats[0].group_name
        total = sum((c.total_amount for c in cats), Decimal(0))
        count = sum(c.transaction_count for c in cats)
        sorted_cats = sorted(cats, key=lambda c: c.total_amount, reverse=True)
        result.append(
            CategoryGroupBreakdown(
                group_id=gid,
                group_name=group_name,
                total_amount=total,
                transaction_count=count,
                categories=sorted_cats,
            )
        )

    return sorted(result, key=lambda g: g.total_amount, reverse=True)
