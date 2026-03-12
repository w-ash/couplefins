from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.transaction import Transaction

_UNCATEGORIZED = "Uncategorized"


@define(frozen=True, slots=True)
class CategoryBreakdown:
    category: str
    group_id: UUID | None
    group_name: str
    total_amount: Decimal
    transaction_count: int


@define(frozen=True, slots=True)
class CategoryGroupBreakdown:
    group_id: UUID | None
    group_name: str
    total_amount: Decimal
    transaction_count: int
    categories: list[CategoryBreakdown]


def build_category_lookup(
    category_mappings: list[CategoryMapping],
    category_groups: list[CategoryGroup],
) -> dict[str, tuple[UUID, str]]:
    group_names = {g.id: g.name for g in category_groups}
    return {
        m.category: (m.group_id, group_names.get(m.group_id, "Unknown"))
        for m in category_mappings
        if m.group_id is not None
    }


def compute_category_breakdowns(
    transactions: list[Transaction],
    category_lookup: dict[str, tuple[UUID, str]],
) -> list[CategoryGroupBreakdown]:
    # Accumulate per category
    cat_amounts: dict[str, Decimal] = {}
    cat_counts: dict[str, int] = {}
    for tx in transactions:
        abs_amount = abs(tx.amount)
        cat_amounts[tx.category] = cat_amounts.get(tx.category, Decimal(0)) + abs_amount
        cat_counts[tx.category] = cat_counts.get(tx.category, 0) + 1

    # Build CategoryBreakdown per category
    category_breakdowns: list[CategoryBreakdown] = []
    for cat, amount in cat_amounts.items():
        gid, gname = category_lookup.get(cat, (None, _UNCATEGORIZED))
        category_breakdowns.append(
            CategoryBreakdown(
                category=cat,
                group_id=gid,
                group_name=gname,
                total_amount=amount,
                transaction_count=cat_counts[cat],
            )
        )

    # Group into CategoryGroupBreakdown
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
