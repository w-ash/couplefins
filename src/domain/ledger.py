"""Settlement ledger — balance-forward accounting across months (v1.7.5).

Outstanding balance = all-time gross positions - all-time payments. Per-month
status is derived by processing months and payments as one chronological
stream through a FIFO queue of open items: a payment (or an opposite-direction
month balance) always relieves the oldest open balance first. Settlement
``year``/``month`` values are display annotations and never enter the math.

All computation happens in a signed space anchored to the UUID-sorted person
pair: positive means "person A (lower UUID) owes person B".
"""

from collections import deque
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from operator import itemgetter
from uuid import UUID

from attrs import define

from src.domain.constants import CoupleDefaults
from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.reconciliation import SettlementResult, compute_gross_settlement

type MonthKey = tuple[int, int]

_ZERO = Decimal(0)

# Month events sort before payment events on the same date.
_MONTH_RANK = 0
_PAYMENT_RANK = 1


class MonthSettlementStatus(StrEnum):
    SETTLED = "settled"
    PARTIALLY_SETTLED = "partially_settled"
    CARRIED_FORWARD = "carried_forward"


@define(frozen=True, slots=True)
class LedgerMonth:
    year: int
    month: int
    gross: (
        SettlementResult | None
    )  # this month's gross position (None/zero-amount => no net debt)
    applied: Decimal  # |gross| already covered (by payments or offsetting months)
    remaining: Decimal  # |gross| - applied
    status: MonthSettlementStatus
    # Payments FIFO says covered this month (any amount), in coverage order.
    covering_settlement_ids: tuple[UUID, ...]
    # True when this month's balance acted as a credit consuming other months.
    is_offset: bool


@define(frozen=True, slots=True)
class PaymentCoverage:
    settlement_id: UUID
    # (year, month, amount) this payment covered, FIFO order.
    covered: tuple[tuple[int, int, Decimal], ...]
    # Portion not matched to any month (reverse payment or overpayment credit).
    unapplied: Decimal


@define(frozen=True, slots=True)
class SettlementLedger:
    outstanding: SettlementResult | None  # None when fully settled
    # Chronological ascending; only months with ≥1 input transaction.
    months: tuple[LedgerMonth, ...]
    payments: tuple[PaymentCoverage, ...]  # chronological by settled_at
    # Σ unapplied across payments (0 when everything matched).
    unapplied_payment_total: Decimal
    # (oldest, newest) non-settled month; None when settled/overpaid.
    span: tuple[MonthKey, MonthKey] | None


@define(frozen=True, slots=True)
class _Event:
    """One chronological ledger event — a month's gross or a payment."""

    month_key: MonthKey | None
    settlement_id: UUID | None
    value: Decimal  # signed; payments carry the negation of their signed value


@define(slots=True)
class _Lot:
    """An open item in the FIFO queue: the unconsumed part of one event."""

    month_key: MonthKey | None
    settlement_id: UUID | None
    sign: int
    remaining: Decimal


@define(frozen=True, slots=True)
class _Allocation:
    """One consumption: an incoming event relieved part of an open lot."""

    consumer_month_key: MonthKey | None
    consumer_settlement_id: UUID | None
    consumed_month_key: MonthKey | None
    consumed_settlement_id: UUID | None
    consumed_sign: int  # the queue lot's sign; the consumer's sign is its negation
    amount: Decimal


def empty_payment_coverage(settlement_id: UUID) -> PaymentCoverage:
    """A coverage that matched nothing — for payments outside any ledger."""
    return PaymentCoverage(settlement_id=settlement_id, covered=(), unapplied=_ZERO)


def sum_settlement_results(
    results: Iterable[SettlementResult | None],
    person_ids: list[UUID],
) -> SettlementResult | None:
    """Direction-aware sum of positions over the UUID-anchored person pair.

    None when the signed total nets to zero (or the couple is incomplete).
    """
    if len(person_ids) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        return None
    person_a, person_b = sorted(person_ids)
    signed = sum((_signed_gross(result, person_a) for result in results), _ZERO)
    return _result_from_signed(signed, person_a, person_b)


def month_remaining_result(month: LedgerMonth) -> SettlementResult | None:
    """The month's remaining balance in its gross direction; None when settled.

    ``remaining > 0`` implies a non-zero gross, so the direction is
    meaningful (a zero-amount gross carries an arbitrary direction).
    """
    if month.gross is None or month.remaining == _ZERO:
        return None
    return SettlementResult(
        amount=month.remaining,
        from_person_id=month.gross.from_person_id,
        to_person_id=month.gross.to_person_id,
    )


def compute_ledger(
    transactions: list[Transaction],
    settlements: Sequence[Settlement],
    person_ids: list[UUID],
) -> SettlementLedger:
    """Compute the running settlement ledger over all-time data.

    Caller passes settlement-relevant transactions (any date range — grouped
    into months internally) and all settlements. Requires exactly two person
    ids; anything else yields an empty ledger.
    """
    if len(person_ids) != CoupleDefaults.EXPECTED_PERSON_COUNT:
        return _empty_ledger()

    person_a, person_b = sorted(person_ids)
    month_gross = {
        key: compute_gross_settlement(txs, person_ids)
        for key, txs in _group_by_month(transactions).items()
    }
    month_signed = {
        key: _signed_gross(gross, person_a) for key, gross in month_gross.items()
    }
    payments = _sorted_payments(settlements)
    queue, allocations = _process_events(
        _build_events(month_signed, payments, person_a)
    )

    outstanding_signed = sum((lot.sign * lot.remaining for lot in queue), _ZERO)
    applied, covering, offset = _allocation_month_effects(
        allocations, _sign(outstanding_signed)
    )
    months = _build_months(month_gross, month_signed, applied, covering, offset)
    coverages, unapplied_total = _build_payment_coverages(payments, allocations, queue)

    return SettlementLedger(
        outstanding=_result_from_signed(outstanding_signed, person_a, person_b),
        months=months,
        payments=coverages,
        unapplied_payment_total=unapplied_total,
        span=_compute_span(months),
    )


def _empty_ledger() -> SettlementLedger:
    return SettlementLedger(
        outstanding=None,
        months=(),
        payments=(),
        unapplied_payment_total=_ZERO,
        span=None,
    )


def _group_by_month(
    transactions: list[Transaction],
) -> dict[MonthKey, list[Transaction]]:
    by_month: dict[MonthKey, list[Transaction]] = {}
    for tx in transactions:
        by_month.setdefault((tx.date.year, tx.date.month), []).append(tx)
    return by_month


def _signed_gross(gross: SettlementResult | None, person_a: UUID) -> Decimal:
    """Signed amount: positive when person A owes person B."""
    if gross is None or gross.amount == _ZERO:
        return _ZERO
    return gross.amount if gross.from_person_id == person_a else -gross.amount


def _signed_payment(settlement: Settlement, person_a: UUID) -> Decimal:
    return (
        settlement.amount
        if settlement.from_person_id == person_a
        else -settlement.amount
    )


def _sign(value: Decimal) -> int:
    if value == _ZERO:
        return 0
    return 1 if value > _ZERO else -1


def _sorted_payments(settlements: Sequence[Settlement]) -> list[Settlement]:
    return sorted(settlements, key=lambda s: (s.settled_at, s.created_at, s.id))


def _build_events(
    month_signed: dict[MonthKey, Decimal],
    payments: list[Settlement],
    person_a: UUID,
) -> list[_Event]:
    """Merge month and payment events into one chronological stream.

    Month events are dated the 1st and sort before payments on the same
    date; payments keep their (settled_at, created_at, id) order via a
    pre-sorted sequence number.
    """
    keyed: list[tuple[tuple[date, int, int], _Event]] = []
    for month_key, signed_gross in month_signed.items():
        if signed_gross == _ZERO:
            continue
        event_date = date(month_key[0], month_key[1], 1)
        keyed.append((
            (event_date, _MONTH_RANK, 0),
            _Event(month_key=month_key, settlement_id=None, value=signed_gross),
        ))
    for seq, settlement in enumerate(payments):
        # A payment from A offsets A-owes-B debt: negate its signed value.
        value = -_signed_payment(settlement, person_a)
        keyed.append((
            (settlement.settled_at.date(), _PAYMENT_RANK, seq),
            _Event(month_key=None, settlement_id=settlement.id, value=value),
        ))
    keyed.sort(key=itemgetter(0))
    return [event for _, event in keyed]


def _process_events(events: list[_Event]) -> tuple[deque[_Lot], list[_Allocation]]:
    """Run the chronological open-item queue.

    Each event consumes opposite-sign lots FIFO; any leftover joins the queue
    as a new lot. All queued lots always share one sign.
    """
    queue: deque[_Lot] = deque()
    allocations: list[_Allocation] = []
    for event in events:
        if event.value == _ZERO:
            continue
        sign = _sign(event.value)
        magnitude = abs(event.value)
        while magnitude > _ZERO and queue and queue[0].sign != sign:
            front = queue[0]
            take = min(magnitude, front.remaining)
            allocations.append(
                _Allocation(
                    consumer_month_key=event.month_key,
                    consumer_settlement_id=event.settlement_id,
                    consumed_month_key=front.month_key,
                    consumed_settlement_id=front.settlement_id,
                    consumed_sign=front.sign,
                    amount=take,
                )
            )
            front.remaining -= take
            magnitude -= take
            if front.remaining == _ZERO:
                queue.popleft()
        if magnitude > _ZERO:
            queue.append(
                _Lot(
                    month_key=event.month_key,
                    settlement_id=event.settlement_id,
                    sign=sign,
                    remaining=magnitude,
                )
            )
    return queue, allocations


def _allocation_month_effects(
    allocations: list[_Allocation],
    outstanding_sign: int,
) -> tuple[dict[MonthKey, Decimal], dict[MonthKey, list[UUID]], set[MonthKey]]:
    """Fold allocations into per-month applied totals, covering payments,
    and the set of months that acted as offsetting credits."""
    applied: dict[MonthKey, Decimal] = {}
    covering: dict[MonthKey, list[UUID]] = {}
    offset: set[MonthKey] = set()
    for allocation in allocations:
        _apply_allocation(allocation, applied, covering, offset, outstanding_sign)
    return applied, covering, offset


def _apply_allocation(
    allocation: _Allocation,
    applied: dict[MonthKey, Decimal],
    covering: dict[MonthKey, list[UUID]],
    offset: set[MonthKey],
    outstanding_sign: int,
) -> None:
    consumer_month = allocation.consumer_month_key
    consumed_month = allocation.consumed_month_key

    if consumer_month is not None:
        applied[consumer_month] = applied.get(consumer_month, _ZERO) + allocation.amount
        if allocation.consumed_settlement_id is not None:
            _append_covering(
                covering, consumer_month, allocation.consumed_settlement_id
            )
    if consumed_month is not None:
        applied[consumed_month] = applied.get(consumed_month, _ZERO) + allocation.amount
        if allocation.consumer_settlement_id is not None:
            _append_covering(
                covering, consumed_month, allocation.consumer_settlement_id
            )
    if consumer_month is not None and consumed_month is not None:
        # The month whose gross direction opposes the eventual outstanding
        # direction acted as the credit. With zero outstanding, fall back to
        # the consumed lot as the debit (the consumer offset it).
        debit_sign = (
            outstanding_sign if outstanding_sign != 0 else allocation.consumed_sign
        )
        offset.add(
            consumed_month if allocation.consumed_sign != debit_sign else consumer_month
        )


def _append_covering(
    covering: dict[MonthKey, list[UUID]], month_key: MonthKey, settlement_id: UUID
) -> None:
    ids = covering.setdefault(month_key, [])
    if settlement_id not in ids:
        ids.append(settlement_id)


def _month_status(magnitude: Decimal, remaining: Decimal) -> MonthSettlementStatus:
    if remaining == _ZERO:
        return MonthSettlementStatus.SETTLED
    if remaining == magnitude:
        return MonthSettlementStatus.CARRIED_FORWARD
    return MonthSettlementStatus.PARTIALLY_SETTLED


def _build_months(
    month_gross: dict[MonthKey, SettlementResult | None],
    month_signed: dict[MonthKey, Decimal],
    applied: dict[MonthKey, Decimal],
    covering: dict[MonthKey, list[UUID]],
    offset: set[MonthKey],
) -> tuple[LedgerMonth, ...]:
    rows: list[LedgerMonth] = []
    for key in sorted(month_gross):
        magnitude = abs(month_signed[key])
        month_applied = applied.get(key, _ZERO)
        remaining = magnitude - month_applied
        rows.append(
            LedgerMonth(
                year=key[0],
                month=key[1],
                gross=month_gross[key],
                applied=month_applied,
                remaining=remaining,
                status=_month_status(magnitude, remaining),
                covering_settlement_ids=tuple(covering.get(key, [])),
                is_offset=key in offset,
            )
        )
    return tuple(rows)


def _build_payment_coverages(
    payments: list[Settlement],
    allocations: list[_Allocation],
    queue: deque[_Lot],
) -> tuple[tuple[PaymentCoverage, ...], Decimal]:
    covered: dict[UUID, list[tuple[int, int, Decimal]]] = {}
    for allocation in allocations:
        pair = _payment_month_pair(allocation)
        if pair is None:
            continue
        settlement_id, month_key = pair
        covered.setdefault(settlement_id, []).append((
            month_key[0],
            month_key[1],
            allocation.amount,
        ))
    unapplied = {
        lot.settlement_id: lot.remaining
        for lot in queue
        if lot.settlement_id is not None
    }
    coverages = tuple(
        PaymentCoverage(
            settlement_id=settlement.id,
            covered=tuple(covered.get(settlement.id, [])),
            unapplied=unapplied.get(settlement.id, _ZERO),
        )
        for settlement in payments
    )
    total = sum((coverage.unapplied for coverage in coverages), _ZERO)
    return coverages, total


def _payment_month_pair(allocation: _Allocation) -> tuple[UUID, MonthKey] | None:
    """The (settlement, month) sides of a payment↔month allocation, either
    direction; None for month↔month and payment↔payment allocations."""
    if (
        allocation.consumer_settlement_id is not None
        and allocation.consumed_month_key is not None
    ):
        return allocation.consumer_settlement_id, allocation.consumed_month_key
    if (
        allocation.consumed_settlement_id is not None
        and allocation.consumer_month_key is not None
    ):
        return allocation.consumed_settlement_id, allocation.consumer_month_key
    return None


def _result_from_signed(
    signed: Decimal, person_a: UUID, person_b: UUID
) -> SettlementResult | None:
    if signed == _ZERO:
        return None
    if signed > _ZERO:
        return SettlementResult(
            amount=signed, from_person_id=person_a, to_person_id=person_b
        )
    return SettlementResult(
        amount=-signed, from_person_id=person_b, to_person_id=person_a
    )


def _compute_span(
    months: tuple[LedgerMonth, ...],
) -> tuple[MonthKey, MonthKey] | None:
    open_keys = [
        (m.year, m.month)
        for m in months
        if m.status is not MonthSettlementStatus.SETTLED
    ]
    if not open_keys:
        return None
    return min(open_keys), max(open_keys)
