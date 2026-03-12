from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.categories import (
    CategoryGroupBreakdown,
    build_category_lookup,
    compute_category_breakdowns,
)
from src.domain.constants import CoupleDefaults
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.category_mapping import CategoryMapping
from src.domain.entities.person import Person
from src.domain.entities.transaction import Transaction
from src.domain.splits import compute_shares


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


def _compute_person_summaries(
    transactions: list[Transaction],
    person_ids: list[UUID],
) -> list[PersonSummary]:
    paid: dict[UUID, Decimal] = {pid: Decimal(0) for pid in person_ids}
    share: dict[UUID, Decimal] = {pid: Decimal(0) for pid in person_ids}
    partner_of = {person_ids[i]: person_ids[1 - i] for i in range(len(person_ids))}

    for tx in transactions:
        payer_share, other_share = compute_shares(tx.amount, tx.payer_percentage)

        other_id = partner_of[tx.payer_person_id]

        if tx.amount < 0:
            # Expense: payer paid the full amount
            paid[tx.payer_person_id] += abs(tx.amount)
            share[tx.payer_person_id] += payer_share
            share[other_id] += other_share
        else:
            # Refund: payer received the refund
            paid[tx.payer_person_id] -= abs(tx.amount)
            share[tx.payer_person_id] -= payer_share
            share[other_id] -= other_share

    return [
        PersonSummary(person_id=pid, total_paid=paid[pid], total_share=share[pid])
        for pid in person_ids
    ]


def _compute_settlement(
    person_summaries: list[PersonSummary],
) -> SettlementResult | None:
    if len(person_summaries) != CoupleDefaults.EXPECTED_PERSON_COUNT:
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

    category_lookup = build_category_lookup(category_mappings, category_groups)
    person_summaries = _compute_person_summaries(shared, person_ids)
    settlement = _compute_settlement(person_summaries)
    breakdowns = compute_category_breakdowns(shared, category_lookup)

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
