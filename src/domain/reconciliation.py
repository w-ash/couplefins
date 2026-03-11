from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from attrs import define

from src.domain.constants import SplitDefaults
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction

_QUANTIZE_EXP = Decimal("0.01")
_HUNDRED = Decimal(100)
_EXPECTED_PERSON_COUNT = 2
_UNCATEGORIZED = "Uncategorized"


@define(frozen=True, slots=True)
class PersonSummary:
    person_id: UUID
    total_paid: Decimal
    total_share: Decimal


@define(frozen=True, slots=True)
class SettlementResult:
    amount: Decimal
    from_person_id: UUID
    to_person_id: UUID


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


@define(frozen=True, slots=True)
class ReconciliationSummary:
    year: int
    month: int
    total_shared_spending: Decimal
    total_shared_refunds: Decimal
    net_shared_spending: Decimal
    person_summaries: list[PersonSummary]
    settlement: SettlementResult | None
    category_group_breakdowns: list[CategoryGroupBreakdown]
    transaction_count: int


def _build_category_lookup(
    category_mappings: list[CategoryMapping],
    category_groups: list[CategoryGroup],
) -> dict[str, tuple[UUID, str]]:
    group_names = {g.id: g.name for g in category_groups}
    return {
        m.category: (m.group_id, group_names.get(m.group_id, "Unknown"))
        for m in category_mappings
        if m.group_id is not None
    }


def _compute_person_summaries(
    transactions: list[Transaction],
    person_ids: list[UUID],
) -> list[PersonSummary]:
    paid: dict[UUID, Decimal] = {pid: Decimal(0) for pid in person_ids}
    share: dict[UUID, Decimal] = {pid: Decimal(0) for pid in person_ids}
    partner_of = {person_ids[i]: person_ids[1 - i] for i in range(len(person_ids))}

    for tx in transactions:
        abs_amount = abs(tx.amount)
        payer_pct = Decimal(
            tx.payer_percentage
            if tx.payer_percentage is not None
            else SplitDefaults.DEFAULT_PAYER_PERCENTAGE
        )
        payer_share = (abs_amount * payer_pct / _HUNDRED).quantize(
            _QUANTIZE_EXP, rounding=ROUND_HALF_UP
        )
        other_share = (abs_amount * (_HUNDRED - payer_pct) / _HUNDRED).quantize(
            _QUANTIZE_EXP, rounding=ROUND_HALF_UP
        )

        other_id = partner_of[tx.payer_person_id]

        if tx.amount < 0:
            # Expense: payer paid the full amount
            paid[tx.payer_person_id] += abs_amount
            share[tx.payer_person_id] += payer_share
            share[other_id] += other_share
        else:
            # Refund: payer received the refund
            paid[tx.payer_person_id] -= abs_amount
            share[tx.payer_person_id] -= payer_share
            share[other_id] -= other_share

    return [
        PersonSummary(person_id=pid, total_paid=paid[pid], total_share=share[pid])
        for pid in person_ids
    ]


def _compute_settlement(
    person_summaries: list[PersonSummary],
) -> SettlementResult | None:
    if len(person_summaries) != _EXPECTED_PERSON_COUNT:
        return None

    p1, p2 = person_summaries
    # net_owed = share - paid. Positive means underpaid (owes money).
    net1 = p1.total_share - p1.total_paid
    net2 = p2.total_share - p2.total_paid

    if net1 == 0 and net2 == 0:
        return SettlementResult(
            amount=Decimal(0), from_person_id=p1.person_id, to_person_id=p2.person_id
        )

    if net1 > 0:
        return SettlementResult(
            amount=net1, from_person_id=p1.person_id, to_person_id=p2.person_id
        )
    return SettlementResult(
        amount=net2, from_person_id=p2.person_id, to_person_id=p1.person_id
    )


def _compute_category_breakdowns(
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


def reconcile(  # noqa: PLR0913
    transactions: list[Transaction],
    persons: list[Person],
    category_mappings: list[CategoryMapping],
    category_groups: list[CategoryGroup],
    *,
    year: int = 0,
    month: int = 0,
) -> ReconciliationSummary:
    person_ids = [p.id for p in persons]

    shared: list[Transaction] = []
    total_spending = Decimal(0)
    total_refunds = Decimal(0)
    for tx in transactions:
        if not tx.is_shared:
            continue
        shared.append(tx)
        abs_amount = abs(tx.amount)
        if tx.amount < 0:
            total_spending += abs_amount
        else:
            total_refunds += abs_amount

    category_lookup = _build_category_lookup(category_mappings, category_groups)
    person_summaries = _compute_person_summaries(shared, person_ids)
    settlement = _compute_settlement(person_summaries)
    breakdowns = _compute_category_breakdowns(shared, category_lookup)

    return ReconciliationSummary(
        year=year,
        month=month,
        total_shared_spending=total_spending,
        total_shared_refunds=total_refunds,
        net_shared_spending=total_spending - total_refunds,
        person_summaries=person_summaries,
        settlement=settlement,
        category_group_breakdowns=breakdowns,
        transaction_count=len(shared),
    )
