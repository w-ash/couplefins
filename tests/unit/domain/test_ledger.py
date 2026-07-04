"""Unit tests for the settlement ledger (v1.7.5).

Signed convention throughout: ALICE has the lower UUID, so positive signed
amounts mean "Alice owes Bob". `month_debt(y, m, v)` builds one transaction
whose gross settles to exactly `v` in that signed space.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

import pytest

from src.domain.entities.settlement import Settlement
from src.domain.entities.transaction import Transaction
from src.domain.exceptions import InvariantViolationError
from src.domain.ledger import (
    MonthSettlementStatus,
    SettlementLedger,
    compute_ledger,
)
from src.domain.reconciliation import (
    SettlementResult,
    compute_gross_settlement,
    compute_net_position,
)
from tests.fixtures.factories import make_settlement, make_transaction

ALICE = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
BOB = uuid.UUID("00000000-0000-0000-0000-0000000000bb")
PERSONS = [ALICE, BOB]

assert sorted(PERSONS) == [ALICE, BOB]  # positive signed == Alice owes Bob


def month_debt(
    year: int, month: int, alice_owes_bob: str, *, day: int = 15
) -> Transaction:
    """One 50/50 transaction whose gross is exactly `alice_owes_bob` signed."""
    net = Decimal(alice_owes_bob)
    payer = BOB if net > 0 else ALICE
    return make_transaction(
        date=date(year, month, day),
        payer_person_id=payer,
        payer_percentage=50,
        amount=-(abs(net) * 2),
    )


def payment(
    amount: str,
    *,
    from_person: uuid.UUID = ALICE,
    settled: datetime | None = None,
    created: datetime | None = None,
    is_waived: bool = False,
    year: int = 2026,
    month: int = 2,
) -> Settlement:
    to_person = BOB if from_person == ALICE else ALICE
    settled_at = settled or datetime(2026, 2, 3, tzinfo=UTC)
    return make_settlement(
        amount=Decimal(amount),
        from_person_id=from_person,
        to_person_id=to_person,
        settled_at=settled_at,
        created_at=created or settled_at,
        is_waived=is_waived,
        year=year,
        month=month,
    )


def signed(result: SettlementResult | None) -> Decimal:
    if result is None or result.amount == 0:
        return Decimal(0)
    return result.amount if result.from_person_id == ALICE else -result.amount


def assert_invariants(
    ledger: SettlementLedger,
    transactions: list[Transaction],
    settlements: list[Settlement],
) -> None:
    """The three construction invariants from the ledger algorithm."""
    total_gross = sum(
        (
            signed(compute_gross_settlement(txs, PERSONS))
            for txs in _by_month(transactions).values()
        ),
        Decimal(0),
    )
    total_payments = sum(
        (s.amount if s.from_person_id == ALICE else -s.amount for s in settlements),
        Decimal(0),
    )
    assert signed(ledger.outstanding) == total_gross - total_payments

    net = compute_net_position(
        compute_gross_settlement(transactions, PERSONS), settlements
    )
    assert signed(ledger.outstanding) == signed(net)

    outstanding_abs = abs(signed(ledger.outstanding))
    remaining_total = sum((m.remaining for m in ledger.months), Decimal(0))
    assert remaining_total + ledger.unapplied_payment_total == outstanding_abs


def _by_month(
    transactions: list[Transaction],
) -> dict[tuple[int, int], list[Transaction]]:
    grouped: dict[tuple[int, int], list[Transaction]] = {}
    for tx in transactions:
        grouped.setdefault((tx.date.year, tx.date.month), []).append(tx)
    return grouped


def test_single_month_full_payment_settles_everything() -> None:
    txs = [month_debt(2026, 1, "50")]
    pay = payment("50")

    ledger = compute_ledger(txs, [pay], PERSONS)

    assert ledger.outstanding is None
    assert len(ledger.months) == 1
    jan = ledger.months[0]
    assert (jan.year, jan.month) == (2026, 1)
    assert jan.status is MonthSettlementStatus.SETTLED
    assert jan.applied == Decimal(50)
    assert jan.remaining == Decimal(0)
    assert jan.covering_settlement_ids == (pay.id,)
    assert jan.is_offset is False
    assert len(ledger.payments) == 1
    assert ledger.payments[0].settlement_id == pay.id
    assert ledger.payments[0].covered == ((2026, 1, Decimal(50)),)
    assert ledger.payments[0].unapplied == Decimal(0)
    assert ledger.unapplied_payment_total == Decimal(0)
    assert ledger.span is None
    assert_invariants(ledger, txs, [pay])


def test_partial_payment_leaves_month_partially_settled() -> None:
    txs = [month_debt(2026, 1, "50")]
    pay = payment("30")

    ledger = compute_ledger(txs, [pay], PERSONS)

    jan = ledger.months[0]
    assert jan.status is MonthSettlementStatus.PARTIALLY_SETTLED
    assert jan.applied == Decimal(30)
    assert jan.remaining == Decimal(20)
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(20), from_person_id=ALICE, to_person_id=BOB
    )
    assert ledger.span == ((2026, 1), (2026, 1))
    assert_invariants(ledger, txs, [pay])


def test_multiple_payments_in_one_month_apply_cumulatively() -> None:
    txs = [month_debt(2026, 1, "90")]
    rent = payment("60", settled=datetime(2026, 2, 1, 8, tzinfo=UTC))
    top_up = payment("60", settled=datetime(2026, 2, 20, tzinfo=UTC))

    ledger = compute_ledger(txs, [top_up, rent], PERSONS)

    jan = ledger.months[0]
    assert jan.status is MonthSettlementStatus.SETTLED
    assert jan.covering_settlement_ids == (rent.id, top_up.id)
    assert ledger.payments[0].settlement_id == rent.id
    assert ledger.payments[0].covered == ((2026, 1, Decimal(60)),)
    assert ledger.payments[0].unapplied == Decimal(0)
    assert ledger.payments[1].settlement_id == top_up.id
    assert ledger.payments[1].covered == ((2026, 1, Decimal(30)),)
    assert ledger.payments[1].unapplied == Decimal(30)
    # Overpaid by 30 — direction flips.
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(30), from_person_id=BOB, to_person_id=ALICE
    )
    assert ledger.span is None
    assert_invariants(ledger, txs, [rent, top_up])


def test_equal_settled_at_tie_breaks_by_created_at() -> None:
    txs = [month_debt(2026, 1, "90")]
    settled = datetime(2026, 2, 5, 12, tzinfo=UTC)
    first = payment(
        "60", settled=settled, created=datetime(2026, 2, 5, 12, 0, 1, tzinfo=UTC)
    )
    second = payment(
        "60", settled=settled, created=datetime(2026, 2, 5, 12, 0, 2, tzinfo=UTC)
    )

    ledger = compute_ledger(txs, [second, first], PERSONS)

    assert ledger.payments[0].settlement_id == first.id
    assert ledger.payments[0].covered == ((2026, 1, Decimal(60)),)
    assert ledger.payments[1].settlement_id == second.id
    assert ledger.payments[1].covered == ((2026, 1, Decimal(30)),)
    assert ledger.payments[1].unapplied == Decimal(30)


def test_payment_settled_in_later_month_covers_old_debt() -> None:
    txs = [month_debt(2026, 1, "50")]
    pay = payment("50", settled=datetime(2026, 4, 10, tzinfo=UTC), month=4)

    ledger = compute_ledger(txs, [pay], PERSONS)

    assert ledger.outstanding is None
    assert ledger.months[0].status is MonthSettlementStatus.SETTLED
    assert ledger.months[0].covering_settlement_ids == (pay.id,)
    assert ledger.payments[0].covered == ((2026, 1, Decimal(50)),)
    assert_invariants(ledger, txs, [pay])


def test_catch_up_payment_covers_three_months_fifo() -> None:
    txs = [
        month_debt(2026, 1, "50"),
        month_debt(2026, 2, "40"),
        month_debt(2026, 3, "30"),
    ]
    pay = payment("100", settled=datetime(2026, 4, 2, tzinfo=UTC), month=4)

    ledger = compute_ledger(txs, [pay], PERSONS)

    jan, feb, mar = ledger.months
    assert jan.status is MonthSettlementStatus.SETTLED
    assert feb.status is MonthSettlementStatus.SETTLED
    assert mar.status is MonthSettlementStatus.PARTIALLY_SETTLED
    assert mar.remaining == Decimal(20)
    assert ledger.payments[0].covered == (
        (2026, 1, Decimal(50)),
        (2026, 2, Decimal(40)),
        (2026, 3, Decimal(10)),
    )
    assert ledger.span == ((2026, 3), (2026, 3))
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(20), from_person_id=ALICE, to_person_id=BOB
    )
    assert_invariants(ledger, txs, [pay])


def test_month_without_transactions_is_absent() -> None:
    txs = [month_debt(2026, 1, "50"), month_debt(2026, 3, "30")]

    ledger = compute_ledger(txs, [], PERSONS)

    assert [(m.year, m.month) for m in ledger.months] == [(2026, 1), (2026, 3)]


def test_month_with_zero_net_gross_is_settled() -> None:
    txs = [
        make_transaction(
            date=date(2026, 1, 5),
            payer_person_id=ALICE,
            payer_percentage=50,
            amount=Decimal("-100.00"),
        ),
        make_transaction(
            date=date(2026, 1, 12),
            payer_person_id=BOB,
            payer_percentage=50,
            amount=Decimal("-100.00"),
        ),
    ]

    ledger = compute_ledger(txs, [], PERSONS)

    jan = ledger.months[0]
    assert jan.status is MonthSettlementStatus.SETTLED
    # Zero-amount gross has arbitrary direction — compare signed, not fields.
    assert signed(jan.gross) == Decimal(0)
    assert jan.applied == Decimal(0)
    assert jan.remaining == Decimal(0)
    assert ledger.outstanding is None
    assert ledger.span is None
    assert_invariants(ledger, txs, [])


def test_offsetting_month_older_than_debt() -> None:
    txs = [month_debt(2026, 1, "-30"), month_debt(2026, 2, "100")]

    ledger = compute_ledger(txs, [], PERSONS)

    jan, feb = ledger.months
    assert jan.status is MonthSettlementStatus.SETTLED
    assert jan.is_offset is True
    assert jan.applied == Decimal(30)
    assert feb.status is MonthSettlementStatus.PARTIALLY_SETTLED
    assert feb.is_offset is False
    assert feb.applied == Decimal(30)
    assert feb.remaining == Decimal(70)
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(70), from_person_id=ALICE, to_person_id=BOB
    )
    assert ledger.span == ((2026, 2), (2026, 2))
    assert_invariants(ledger, txs, [])


def test_offsetting_month_newer_than_debt() -> None:
    txs = [
        month_debt(2026, 1, "100"),
        month_debt(2026, 2, "50"),
        month_debt(2026, 3, "-30"),
    ]

    ledger = compute_ledger(txs, [], PERSONS)

    jan, feb, mar = ledger.months
    assert jan.status is MonthSettlementStatus.PARTIALLY_SETTLED
    assert jan.remaining == Decimal(70)
    assert feb.status is MonthSettlementStatus.CARRIED_FORWARD
    assert feb.remaining == Decimal(50)
    assert mar.status is MonthSettlementStatus.SETTLED
    assert mar.is_offset is True
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(120), from_person_id=ALICE, to_person_id=BOB
    )
    assert ledger.span == ((2026, 1), (2026, 2))
    assert_invariants(ledger, txs, [])


def test_mixed_directions_netting_to_zero() -> None:
    txs = [month_debt(2026, 1, "100"), month_debt(2026, 2, "-100")]

    ledger = compute_ledger(txs, [], PERSONS)

    assert ledger.outstanding is None
    assert all(m.status is MonthSettlementStatus.SETTLED for m in ledger.months)
    assert ledger.span is None
    assert_invariants(ledger, txs, [])


def test_overpayment_flips_outstanding_direction() -> None:
    txs = [month_debt(2026, 1, "50")]
    pay = payment("80")

    ledger = compute_ledger(txs, [pay], PERSONS)

    assert ledger.outstanding == SettlementResult(
        amount=Decimal(30), from_person_id=BOB, to_person_id=ALICE
    )
    assert ledger.months[0].status is MonthSettlementStatus.SETTLED
    assert ledger.span is None
    assert ledger.unapplied_payment_total == Decimal(30)
    assert ledger.payments[0].unapplied == Decimal(30)
    assert_invariants(ledger, txs, [pay])


def test_reverse_payment_smaller_than_debt() -> None:
    # Bob (the creditor) pays Alice while Alice owes Bob — debt grows.
    txs = [month_debt(2026, 1, "50")]
    pay = payment("20", from_person=BOB)

    ledger = compute_ledger(txs, [pay], PERSONS)

    jan = ledger.months[0]
    assert jan.status is MonthSettlementStatus.CARRIED_FORWARD
    assert jan.remaining == Decimal(50)
    assert ledger.payments[0].covered == ()
    assert ledger.payments[0].unapplied == Decimal(20)
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(70), from_person_id=ALICE, to_person_id=BOB
    )
    assert_invariants(ledger, txs, [pay])


def test_reverse_payment_larger_than_opposite_credit() -> None:
    # Jan: Bob owes Alice 10. Bob then pays 30 — more than his credit —
    # before Feb's debt lands. The payment covers Jan's balance FIFO and
    # carries 20 unapplied.
    txs = [month_debt(2026, 1, "-10"), month_debt(2026, 2, "50")]
    pay = payment("30", from_person=BOB, settled=datetime(2026, 1, 20, tzinfo=UTC))

    ledger = compute_ledger(txs, [pay], PERSONS)

    jan, feb = ledger.months
    assert jan.status is MonthSettlementStatus.SETTLED
    assert jan.covering_settlement_ids == (pay.id,)
    assert ledger.payments[0].covered == ((2026, 1, Decimal(10)),)
    assert ledger.payments[0].unapplied == Decimal(20)
    assert feb.status is MonthSettlementStatus.CARRIED_FORWARD
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(70), from_person_id=ALICE, to_person_id=BOB
    )
    assert_invariants(ledger, txs, [pay])


def test_waived_settlement_participates_identically() -> None:
    txs = [month_debt(2026, 1, "50")]
    waiver = payment("50", is_waived=True)

    ledger = compute_ledger(txs, [waiver], PERSONS)

    assert ledger.outstanding is None
    assert ledger.months[0].status is MonthSettlementStatus.SETTLED
    assert ledger.months[0].covering_settlement_ids == (waiver.id,)

    # A late edit adds more January spending — the difference resurfaces.
    changed = [*txs, month_debt(2026, 1, "25", day=28)]
    reledger = compute_ledger(changed, [waiver], PERSONS)

    assert reledger.outstanding == SettlementResult(
        amount=Decimal(25), from_person_id=ALICE, to_person_id=BOB
    )
    assert reledger.months[0].status is MonthSettlementStatus.PARTIALLY_SETTLED
    assert reledger.months[0].remaining == Decimal(25)
    assert_invariants(reledger, changed, [waiver])


def test_settlements_without_any_transactions_are_pure_credit() -> None:
    pay = payment("40")

    ledger = compute_ledger([], [pay], PERSONS)

    assert ledger.months == ()
    assert ledger.outstanding == SettlementResult(
        amount=Decimal(40), from_person_id=BOB, to_person_id=ALICE
    )
    assert ledger.payments[0].covered == ()
    assert ledger.payments[0].unapplied == Decimal(40)
    assert ledger.unapplied_payment_total == Decimal(40)
    assert ledger.span is None
    assert_invariants(ledger, [], [pay])


def test_many_months_all_fully_settled() -> None:
    txs = [
        month_debt(2026, 1, "50"),
        month_debt(2026, 2, "40"),
        month_debt(2026, 3, "30"),
    ]
    pays = [
        payment("50", settled=datetime(2026, 2, 3, tzinfo=UTC)),
        payment("40", settled=datetime(2026, 3, 3, tzinfo=UTC), month=3),
        payment("30", settled=datetime(2026, 4, 3, tzinfo=UTC), month=4),
    ]

    ledger = compute_ledger(txs, pays, PERSONS)

    assert ledger.outstanding is None
    assert all(m.status is MonthSettlementStatus.SETTLED for m in ledger.months)
    assert ledger.span is None
    assert ledger.unapplied_payment_total == Decimal(0)
    assert_invariants(ledger, txs, pays)


def test_settlement_year_month_annotation_never_enters_math() -> None:
    txs = [month_debt(2026, 1, "50"), month_debt(2026, 2, "40")]
    settled = datetime(2026, 3, 1, tzinfo=UTC)
    settlement_id = uuid.uuid4()

    def annotated(year: int | None, month: int | None) -> Settlement:
        return make_settlement(
            id=settlement_id,
            amount=Decimal(60),
            from_person_id=ALICE,
            to_person_id=BOB,
            settled_at=settled,
            created_at=settled,
            year=year,
            month=month,
        )

    correct = compute_ledger(txs, [annotated(2026, 3)], PERSONS)
    wrong = compute_ledger(txs, [annotated(2025, 7)], PERSONS)
    unannotated = compute_ledger(txs, [annotated(None, None)], PERSONS)

    assert correct == wrong
    assert correct == unannotated


class _Lcg:
    """Tiny deterministic LCG — seeded pseudo-random scenarios without
    the `random` module (flagged by S311 even for non-crypto use)."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def next_int(self, low: int, high: int) -> int:
        self._state = (self._state * 48271 + 1) % 2147483647
        return low + self._state % (high - low + 1)


def test_seeded_random_scenarios_hold_invariants() -> None:
    rng = _Lcg(42)
    for _ in range(25):
        txs: list[Transaction] = []
        for month in range(1, 7):
            if rng.next_int(0, 9) < 3:
                continue  # skipped month
            net = rng.next_int(-200, 200)
            if net == 0:
                continue
            txs.append(month_debt(2026, month, str(net)))
        pays = [
            payment(
                str(rng.next_int(1, 250)),
                from_person=PERSONS[rng.next_int(0, 1)],
                settled=datetime(
                    2026, rng.next_int(1, 7), rng.next_int(1, 28), tzinfo=UTC
                ),
            )
            for _ in range(rng.next_int(0, 4))
        ]

        ledger = compute_ledger(txs, pays, PERSONS)

        assert_invariants(ledger, txs, pays)


def test_wrong_person_count_returns_empty_ledger() -> None:
    txs = [month_debt(2026, 1, "50")]
    pays = [payment("20")]

    for person_ids in ([ALICE], [ALICE, BOB, uuid.uuid4()]):
        ledger = compute_ledger(txs, pays, person_ids)

        assert ledger.outstanding is None
        assert ledger.months == ()
        assert ledger.payments == ()
        assert ledger.unapplied_payment_total == Decimal(0)
        assert ledger.span is None


def test_invariant_violation_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: object, **kwargs: object) -> SettlementResult | None:
        raise InvariantViolationError("zero-sum broken")

    monkeypatch.setattr("src.domain.ledger.compute_gross_settlement", explode)

    with pytest.raises(InvariantViolationError):
        compute_ledger([month_debt(2026, 1, "50")], [], PERSONS)
