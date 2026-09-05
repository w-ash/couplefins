from decimal import Decimal
from uuid import UUID

from attrs import Factory, define

from src.domain.entities.category import Category
from src.domain.entities.category_group import (
    CategoryGroup,
    GroupKind,
    is_spending_kind,
)


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


def get_category_kinds(
    categories: list[Category],
    category_groups: list[CategoryGroup],
) -> dict[str, GroupKind]:
    """Each mapped category's group kind, by category name."""
    kinds: dict[UUID, GroupKind] = {g.id: g.kind for g in category_groups}
    result: dict[str, GroupKind] = {}
    for c in categories:
        if c.group_id is None:
            continue
        kind = kinds.get(c.group_id)
        if kind is not None:
            result[c.name] = kind
    return result


def get_non_spending_categories(
    categories: list[Category],
    category_groups: list[CategoryGroup],
) -> frozenset[str]:
    """Names of categories whose group is not spending: money movement
    (transfer) or money coming in (income)."""
    return frozenset(
        name
        for name, kind in get_category_kinds(categories, category_groups).items()
        if not is_spending_kind(kind)
    )


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
