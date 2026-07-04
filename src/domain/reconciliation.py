from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from attrs import define

from src.domain.categories import (
    CategoryGroupBreakdown,
    build_category_lookup,
    compute_category_breakdowns,
)
from src.domain.constants import (
    UNCATEGORIZED_GROUP_NAME,
    CoupleDefaults,
    SplitDefaults,
)
from src.domain.date_math import month_bounds
from src.domain.entities.category import Category
from src.domain.entities.category_group import CategoryGroup
from src.domain.entities.person import Person
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.filters import is_reconciliation_relevant
from src.domain.splits import compute_shares


@define(frozen=True, slots=True)
class PersonSummary:
    person_id: UUID
    total_paid: Decimal
    total_share: Decimal


@define(frozen=True, slots=True)
class PayerSplitSummary:
    """Per-payer aggregate for the Settle Up audit table.

    `total_share` here is the payer's share of the bills *they* fronted —
    NOT their share across all bills (which is what `PersonSummary` tracks
    for the broader reconcile-then-settle math). With this semantics each
    audit row stands alone: `total_paid - total_share = partner_share`.
    """

    payer_person_id: UUID
    total_paid: Decimal
    total_share: Decimal
    transaction_count: int


@define(frozen=True, slots=True)
class PayerGroupSummary:
    """Same semantics as PayerSplitSummary, sliced by category-group."""

    payer_person_id: UUID
    group_id: UUID | None
    group_name: str
    total_paid: Decimal
    total_share: Decimal
    transaction_count: int
    # Distinct category names aggregated into this row — the exact filter
    # payload a drill-through link needs (also covers Uncategorized rows,
    # whose categories belong to no group).
    categories: list[str]


@define(frozen=True, slots=True)
class SettlementResult:
    amount: Decimal
    from_person_id: UUID
    to_person_id: UUID


@define(frozen=True, slots=True)
class ReconciliationSummary:
    start_date: date
    end_date: date
    total_household_spending: Decimal
    total_household_refunds: Decimal
    net_household_spending: Decimal
    person_summaries: list[PersonSummary]
    settlement: SettlementResult | None
    category_group_breakdowns: list[CategoryGroupBreakdown]
    transaction_count: int
    # Filtered split list — exposed so callers (e.g., audit-table builders)
    # can reuse it without re-filtering the same transactions.
    split_transactions: list[Transaction]
    # Category → (group_id, group_name) lookup — exposed so callers reuse it
    # instead of rebuilding the identical dict in the same request.
    category_lookup: dict[str, tuple[UUID, str]]


def filter_split_transactions(
    transactions: list[Transaction],
) -> list[Transaction]:
    """Transactions that participate in settlement math.

    Excludes excluded rows, settlement transfers, and household-no-split
    (payer_percentage == 100, which means the payer absorbs the whole bill
    and nothing is owed back).
    """
    return [
        tx
        for tx in transactions
        if is_reconciliation_relevant(tx)
        and tx.payer_percentage < SplitDefaults.MAX_PAYER_PERCENTAGE
    ]


def _compute_person_summaries(
    transactions: list[Transaction],
    person_ids: list[UUID],
) -> list[PersonSummary]:
    paid: dict[UUID, Decimal] = dict.fromkeys(person_ids, Decimal(0))
    share: dict[UUID, Decimal] = dict.fromkeys(person_ids, Decimal(0))
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


def compute_payer_split_summaries(
    transactions: list[Transaction],
    person_ids: list[UUID],
) -> list[PayerSplitSummary]:
    """Per-payer aggregates over an already-filtered split list."""
    paid: dict[UUID, Decimal] = dict.fromkeys(person_ids, Decimal(0))
    share: dict[UUID, Decimal] = dict.fromkeys(person_ids, Decimal(0))
    counts: dict[UUID, int] = dict.fromkeys(person_ids, 0)

    for tx in transactions:
        payer_share, _ = compute_shares(tx.amount, tx.payer_percentage)
        sign = Decimal(1) if tx.amount < 0 else Decimal(-1)
        paid[tx.payer_person_id] += sign * abs(tx.amount)
        share[tx.payer_person_id] += sign * payer_share
        counts[tx.payer_person_id] += 1

    return [
        PayerSplitSummary(
            payer_person_id=pid,
            total_paid=paid[pid],
            total_share=share[pid],
            transaction_count=counts[pid],
        )
        for pid in person_ids
    ]


type _PayerGroupKey = tuple[UUID, UUID | None]


def compute_payer_group_summaries(
    transactions: list[Transaction],
    person_ids: list[UUID],
    category_lookup: dict[str, tuple[UUID, str]],
) -> list[PayerGroupSummary]:
    """Per-(payer x category-group) split aggregates.

    Each cell tracks bills the row's person fronted and their share of those
    bills. `partner_share` for an audit row is derived as `paid - share` — the
    amount the partner owes for the bills this person fronted.

    Caller passes an already-filtered split list (see
    `filter_split_transactions`). Output ordering: groups by absolute total
    descending, then by `person_ids` order. Uncategorized rows sort last.
    """
    paid: dict[_PayerGroupKey, Decimal] = {}
    share: dict[_PayerGroupKey, Decimal] = {}
    counts: dict[_PayerGroupKey, int] = {}
    cats: dict[_PayerGroupKey, set[str]] = {}
    group_names: dict[UUID | None, str] = {}

    for tx in transactions:
        payer_share, _ = compute_shares(tx.amount, tx.payer_percentage)
        gid, gname = category_lookup.get(tx.category, (None, UNCATEGORIZED_GROUP_NAME))
        group_names[gid] = gname
        key: _PayerGroupKey = (tx.payer_person_id, gid)
        sign = Decimal(1) if tx.amount < 0 else Decimal(-1)
        paid[key] = paid.get(key, Decimal(0)) + sign * abs(tx.amount)
        share[key] = share.get(key, Decimal(0)) + sign * payer_share
        counts[key] = counts.get(key, 0) + 1
        cats.setdefault(key, set()).add(tx.category)

    group_totals: dict[UUID | None, Decimal] = {}
    for (_pid, gid), amount in paid.items():
        group_totals[gid] = group_totals.get(gid, Decimal(0)) + abs(amount)

    def _group_sort_key(gid: UUID | None) -> tuple[int, Decimal]:
        return (1 if gid is None else 0, -group_totals.get(gid, Decimal(0)))

    rows: list[PayerGroupSummary] = []
    for gid in sorted(group_totals.keys(), key=_group_sort_key):
        for pid in person_ids:
            key = (pid, gid)
            if key not in counts:
                continue
            rows.append(
                PayerGroupSummary(
                    payer_person_id=pid,
                    group_id=gid,
                    group_name=group_names[gid],
                    total_paid=paid[key],
                    total_share=share[key],
                    transaction_count=counts[key],
                    categories=sorted(cats[key]),
                )
            )

    return rows


def _compute_settlement(
    person_summaries: list[PersonSummary],
) -> SettlementResult | None:
    if len(person_summaries) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        return None

    p1, p2 = person_summaries
    # net_owed = share - paid. Positive means underpaid (owes money).
    net1 = p1.total_share - p1.total_paid
    net2 = p2.total_share - p2.total_paid

    if net1 + net2 != Decimal(0):
        raise InvariantViolationError(
            f"Zero-sum invariant violated: net1={net1}, net2={net2}, sum={net1 + net2}"
        )

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


def compute_gross_settlement(
    transactions: list[Transaction],
    person_ids: list[UUID],
) -> SettlementResult | None:
    """Gross settlement over any transaction set, independent of reconcile().

    For callers whose settlement universe differs from their display set
    (e.g. scoped views): applies filter_split_transactions, so passing an
    unfiltered fetch is safe.
    """
    splits = filter_split_transactions(transactions)
    return _compute_settlement(_compute_person_summaries(splits, person_ids))


def compute_net_position(
    gross: SettlementResult | None,
    settlements: Sequence[Settlement],
) -> SettlementResult | None:
    """Apply settlement payments to gross balance. Overpayments reverse direction."""
    if gross is None or not settlements:
        return gross

    net = gross.amount
    for s in settlements:
        if s.from_person_id == gross.from_person_id:
            net -= s.amount
        else:
            net += s.amount

    if net == Decimal(0):
        return None

    if net > 0:
        return SettlementResult(
            amount=net,
            from_person_id=gross.from_person_id,
            to_person_id=gross.to_person_id,
        )

    return SettlementResult(
        amount=abs(net),
        from_person_id=gross.to_person_id,
        to_person_id=gross.from_person_id,
    )


def reconcile(
    transactions: list[Transaction],
    persons: list[Person],
    categories: list[Category],
    category_groups: list[CategoryGroup],
    *,
    start_date: date,
    end_date: date,
) -> ReconciliationSummary:
    person_ids = [p.id for p in persons]

    household = filter_split_transactions(transactions)
    total_spending = Decimal(0)
    total_refunds = Decimal(0)
    for tx in household:
        abs_amount = abs(tx.amount)
        if tx.amount < 0:
            total_spending += abs_amount
        else:
            total_refunds += abs_amount

    category_lookup = build_category_lookup(categories, category_groups)
    person_summaries = _compute_person_summaries(household, person_ids)
    settlement = _compute_settlement(person_summaries)
    breakdowns = compute_category_breakdowns(household, category_lookup)

    return ReconciliationSummary(
        start_date=start_date,
        end_date=end_date,
        total_household_spending=total_spending,
        total_household_refunds=total_refunds,
        net_household_spending=total_spending - total_refunds,
        person_summaries=person_summaries,
        settlement=settlement,
        category_group_breakdowns=breakdowns,
        transaction_count=len(household),
        split_transactions=household,
        category_lookup=category_lookup,
    )


def reconcile_all_months(
    by_month: dict[int, list[Transaction]],
    persons: list[Person],
    categories: list[Category],
    category_groups: list[CategoryGroup],
    year: int,
) -> dict[int, ReconciliationSummary]:
    results: dict[int, ReconciliationSummary] = {}
    for month, txs in by_month.items():
        start, end = month_bounds(year, month)
        results[month] = reconcile(
            txs, persons, categories, category_groups, start_date=start, end_date=end
        )
    return results
