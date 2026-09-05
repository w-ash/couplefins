"""Unit tests for the settlement ledger (v1.11.0 — explicit portions).

Signed convention throughout: ALICE.id has the lower UUID, so positive signed
amounts mean "Alice owes Bob". `month_debt(y, m, v)` builds one transaction
whose gross settles to exactly `v` in that signed space.

The production fixture mirrors prod verbatim (Alice standing in for Ash,
Bob for Kew): three $1,981 payments, each covering its own rent month.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import ClassVar
import uuid

from src.domain.entities.settlement import Settlement
from src.domain.entities.settlement_portion import SettlementPortion
from src.domain.entities.transaction import Transaction
from src.domain.ledger import (
    LedgerMonth,
    MonthSettlementStatus,
    SettlementLedger,
    compute_ledger,
    empty_ledger_year,
    plan_portions,
    sum_settlement_results,
)
from src.domain.reconciliation import SettlementResult
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_settlement,
    make_settlement_portion,
    make_transaction,
)

PERSONS = [ALICE.id, BOB.id]

assert sorted(PERSONS) == [ALICE.id, BOB.id]  # positive signed == Alice owes Bob


def month_debt(
    year: int, month: int, alice_owes_bob: str, *, day: int = 15
) -> Transaction:
    """One 50/50 transaction whose gross is exactly `alice_owes_bob` signed."""
    net = Decimal(alice_owes_bob)
    payer = BOB.id if net > 0 else ALICE.id
    return make_transaction(
        date=date(year, month, day),
        payer_person_id=payer,
        payer_percentage=50,
        amount=-(abs(net) * 2),
    )


def payment(
    amount: str,
    *,
    from_person: uuid.UUID = ALICE.id,
    settled: datetime | None = None,
    is_waived: bool = False,
) -> Settlement:
    to_person = BOB.id if from_person == ALICE.id else ALICE.id
    settled_at = settled or datetime(2026, 2, 3, tzinfo=UTC)
    return make_settlement(
        amount=Decimal(amount),
        from_person_id=from_person,
        to_person_id=to_person,
        settled_at=settled_at,
        created_at=settled_at,
        is_waived=is_waived,
    )


def portions_for(
    settlement: Settlement, *slices: tuple[int, int, str]
) -> list[SettlementPortion]:
    return [
        make_settlement_portion(
            settlement_id=settlement.id,
            year=year,
            month=month,
            amount=Decimal(amount),
        )
        for year, month, amount in slices
    ]


def signed(result: SettlementResult | None) -> Decimal:
    if result is None or result.amount == 0:
        return Decimal(0)
    return result.amount if result.from_person_id == ALICE.id else -result.amount


def month_row(ledger: SettlementLedger, year: int, month: int) -> LedgerMonth:
    return next(m for m in ledger.months if (m.year, m.month) == (year, month))


class TestEmptyAndDegenerate:
    def test_no_data_yields_empty_ledger(self) -> None:
        ledger = compute_ledger([], [], [], PERSONS)
        assert ledger.outstanding is None
        assert ledger.months == ()
        assert ledger.years == ()
        assert ledger.settlements == ()
        assert ledger.span is None

    def test_wrong_person_count_yields_empty_ledger(self) -> None:
        ledger = compute_ledger([month_debt(2026, 1, "100")], [], [], [ALICE.id])
        assert ledger.outstanding is None
        assert ledger.months == ()

    def test_sum_settlement_results_requires_couple(self) -> None:
        assert sum_settlement_results([], [ALICE.id]) is None


class TestCharges:
    def test_month_charged_is_net_of_shares(self) -> None:
        ledger = compute_ledger(
            [month_debt(2026, 1, "100"), month_debt(2026, 1, "-30")],
            [],
            [],
            PERSONS,
        )
        row = month_row(ledger, 2026, 1)
        assert signed(row.charged) == Decimal(70)
        assert signed(row.balance) == Decimal(70)
        assert row.status is MonthSettlementStatus.CARRIED_FORWARD

    def test_refund_reduces_charges(self) -> None:
        refund = make_transaction(
            date=date(2026, 1, 20),
            payer_person_id=BOB.id,
            payer_percentage=50,
            amount=Decimal(40),  # positive = refund; Alice's share drops 20
        )
        ledger = compute_ledger([month_debt(2026, 1, "100"), refund], [], [], PERSONS)
        assert signed(month_row(ledger, 2026, 1).charged) == Decimal(80)

    def test_settlement_transfers_and_full_share_rows_excluded(self) -> None:
        transfer = make_transaction(
            date=date(2026, 1, 5),
            payer_person_id=ALICE.id,
            payer_percentage=100,
            amount=Decimal(-50),
            is_settlement=True,
        )
        no_split = make_transaction(
            date=date(2026, 1, 6),
            payer_person_id=ALICE.id,
            payer_percentage=100,
            amount=Decimal(-80),
        )
        ledger = compute_ledger(
            [month_debt(2026, 1, "100"), transfer, no_split], [], [], PERSONS
        )
        assert signed(month_row(ledger, 2026, 1).charged) == Decimal(100)

    def test_zero_net_month_reads_settled(self) -> None:
        ledger = compute_ledger(
            [month_debt(2026, 1, "50"), month_debt(2026, 1, "-50")],
            [],
            [],
            PERSONS,
        )
        row = month_row(ledger, 2026, 1)
        assert row.charged is None
        assert row.balance is None
        assert row.status is MonthSettlementStatus.SETTLED


class TestPortionApplication:
    def test_portion_settles_its_month(self) -> None:
        pay = payment("100")
        ledger = compute_ledger(
            [month_debt(2026, 1, "100")],
            [pay],
            portions_for(pay, (2026, 1, "100")),
            PERSONS,
        )
        row = month_row(ledger, 2026, 1)
        assert row.balance is None
        assert row.status is MonthSettlementStatus.SETTLED
        assert ledger.outstanding is None

    def test_partial_portion_leaves_remainder(self) -> None:
        pay = payment("60")
        ledger = compute_ledger(
            [month_debt(2026, 1, "100")],
            [pay],
            portions_for(pay, (2026, 1, "60")),
            PERSONS,
        )
        row = month_row(ledger, 2026, 1)
        assert signed(row.paid) == Decimal(60)
        assert signed(row.balance) == Decimal(40)
        assert row.status is MonthSettlementStatus.PARTIALLY_SETTLED

    def test_month_paid_past_charges_swings_direction(self) -> None:
        """The normal state: a month settled in full routinely swings."""
        pay = payment("1981.00")
        ledger = compute_ledger(
            [month_debt(2026, 1, "1956.89")],
            [pay],
            portions_for(pay, (2026, 1, "1981.00")),
            PERSONS,
        )
        row = month_row(ledger, 2026, 1)
        assert row.balance is not None
        assert row.balance.amount == Decimal("24.11")
        assert row.balance.from_person_id == BOB.id  # direction flipped
        assert row.status is MonthSettlementStatus.PARTIALLY_SETTLED

    def test_reverse_direction_payment_adds_to_debt(self) -> None:
        pay = payment("30", from_person=BOB.id)
        ledger = compute_ledger(
            [month_debt(2026, 1, "100")],
            [pay],
            portions_for(pay, (2026, 1, "30")),
            PERSONS,
        )
        assert signed(month_row(ledger, 2026, 1).balance) == Decimal(130)

    def test_portionless_settlement_covers_settled_at_month(self) -> None:
        pay = payment("100", settled=datetime(2026, 3, 9, tzinfo=UTC))
        ledger = compute_ledger([month_debt(2026, 3, "100")], [pay], [], PERSONS)
        assert month_row(ledger, 2026, 3).balance is None
        entry = ledger.settlements[0]
        assert [(p.year, p.month, p.amount) for p in entry.portions] == [
            (2026, 3, Decimal(100))
        ]

    def test_waived_settlement_applies_like_any_payment(self) -> None:
        waiver = payment("100", is_waived=True)
        ledger = compute_ledger(
            [month_debt(2026, 1, "100")],
            [waiver],
            portions_for(waiver, (2026, 1, "100")),
            PERSONS,
        )
        assert month_row(ledger, 2026, 1).status is MonthSettlementStatus.SETTLED

    def test_portion_only_month_appears_in_ledger(self) -> None:
        pay = payment("50")
        ledger = compute_ledger([], [pay], portions_for(pay, (2026, 4, "50")), PERSONS)
        row = month_row(ledger, 2026, 4)
        assert row.charged is None
        assert signed(row.balance) == Decimal(-50)


class TestSettlementEntries:
    def test_portions_sort_ascending_by_month(self) -> None:
        pay = payment("90")
        ledger = compute_ledger(
            [month_debt(2026, 1, "60"), month_debt(2026, 2, "30")],
            [pay],
            portions_for(pay, (2026, 2, "30"), (2026, 1, "60")),
            PERSONS,
        )
        entry = ledger.settlements[0]
        assert [(p.year, p.month) for p in entry.portions] == [(2026, 1), (2026, 2)]

    def test_entries_are_chronological(self) -> None:
        first = payment("10", settled=datetime(2026, 1, 5, tzinfo=UTC))
        second = payment("20", settled=datetime(2026, 2, 5, tzinfo=UTC))
        ledger = compute_ledger([], [second, first], [], PERSONS)
        assert [e.settlement_id for e in ledger.settlements] == [first.id, second.id]


class TestYears:
    def test_year_totals_sum_its_months(self) -> None:
        pay = payment("100")
        ledger = compute_ledger(
            [month_debt(2026, 1, "100"), month_debt(2026, 3, "40")],
            [pay],
            portions_for(pay, (2026, 1, "100")),
            PERSONS,
        )
        year = ledger.years[0]
        assert year.year == 2026
        assert signed(year.charged) == Decimal(140)
        assert signed(year.paid) == Decimal(100)
        assert signed(year.balance) == Decimal(40)
        assert year.span == ((2026, 1), (2026, 3))

    def test_january_payment_with_december_portion_counts_toward_old_year(
        self,
    ) -> None:
        pay = payment("80", settled=datetime(2027, 1, 4, tzinfo=UTC))
        ledger = compute_ledger(
            [month_debt(2026, 12, "80")],
            [pay],
            portions_for(pay, (2026, 12, "80")),
            PERSONS,
        )
        year_2026 = next(y for y in ledger.years if y.year == 2026)
        assert signed(year_2026.paid) == Decimal(80)
        assert year_2026.balance is None
        assert all(y.year == 2026 for y in ledger.years)

    def test_empty_ledger_year_is_blank(self) -> None:
        row = empty_ledger_year(2027)
        assert row.year == 2027
        assert row.charged is None
        assert row.balance is None
        assert row.span is None


class TestOutstandingInvariants:
    def test_outstanding_is_sum_of_month_balances(self) -> None:
        pay = payment("70")
        ledger = compute_ledger(
            [month_debt(2026, 1, "100"), month_debt(2026, 2, "-20")],
            [pay],
            portions_for(pay, (2026, 1, "70")),
            PERSONS,
        )
        month_sum = sum(signed(m.balance) for m in ledger.months)
        year_sum = sum(signed(y.balance) for y in ledger.years)
        assert signed(ledger.outstanding) == month_sum == year_sum == Decimal(10)

    def test_span_covers_open_months_only(self) -> None:
        pay = payment("100")
        ledger = compute_ledger(
            [
                month_debt(2026, 1, "100"),
                month_debt(2026, 2, "50"),
                month_debt(2026, 4, "25"),
            ],
            [pay],
            portions_for(pay, (2026, 1, "100")),
            PERSONS,
        )
        assert ledger.span == ((2026, 2), (2026, 4))


class TestPlanPortions:
    def test_single_covered_month_takes_full_amount(self) -> None:
        ledger = compute_ledger([month_debt(2026, 1, "1956.89")], [], [], PERSONS)
        plans = plan_portions(ledger.months, Decimal("1981.00"), ALICE.id, [(2026, 1)])
        assert [(p.year, p.month, p.amount) for p in plans] == [
            (2026, 1, Decimal("1981.00"))
        ]

    def test_lump_clears_covered_months_oldest_first(self) -> None:
        ledger = compute_ledger(
            [month_debt(2026, 1, "60"), month_debt(2026, 2, "30")],
            [],
            [],
            PERSONS,
        )
        plans = plan_portions(
            ledger.months, Decimal(80), ALICE.id, [(2026, 2), (2026, 1)]
        )
        assert [(p.year, p.month, p.amount) for p in plans] == [
            (2026, 1, Decimal(60)),
            (2026, 2, Decimal(20)),
        ]

    def test_surplus_lands_on_newest_covered_month(self) -> None:
        ledger = compute_ledger(
            [month_debt(2026, 1, "60"), month_debt(2026, 2, "30")],
            [],
            [],
            PERSONS,
        )
        plans = plan_portions(
            ledger.months, Decimal(100), ALICE.id, [(2026, 1), (2026, 2)]
        )
        assert [(p.year, p.month, p.amount) for p in plans] == [
            (2026, 1, Decimal(60)),
            (2026, 2, Decimal(40)),
        ]
        assert sum(p.amount for p in plans) == Decimal(100)

    def test_skips_months_owed_in_the_other_direction(self) -> None:
        ledger = compute_ledger(
            [month_debt(2026, 1, "-40"), month_debt(2026, 2, "50")],
            [],
            [],
            PERSONS,
        )
        plans = plan_portions(
            ledger.months, Decimal(50), ALICE.id, [(2026, 1), (2026, 2)]
        )
        assert [(p.year, p.month, p.amount) for p in plans] == [(2026, 2, Decimal(50))]

    def test_unknown_month_still_receives_remainder(self) -> None:
        plans = plan_portions([], Decimal(25), ALICE.id, [(2026, 6)])
        assert [(p.year, p.month, p.amount) for p in plans] == [(2026, 6, Decimal(25))]

    def test_empty_covered_months_plans_nothing(self) -> None:
        assert plan_portions([], Decimal(25), ALICE.id, []) == ()


class TestProductionFixture:
    """The verified 2026 acceptance table, Alice standing in for Ash."""

    charges: ClassVar[list[tuple[str, str]]] = [
        ("2026-01", "1956.89"),
        ("2026-02", "222.31"),
        ("2026-03", "1805.10"),
    ]

    def _ledger(self) -> SettlementLedger:
        transactions = [
            month_debt(int(label[:4]), int(label[5:7]), amount)
            for label, amount in self.charges
        ]
        payments = []
        portions: list[SettlementPortion] = []
        for month in (1, 2, 3):
            pay = payment("1981.00", settled=datetime(2026, 4, 26, tzinfo=UTC))
            payments.append(pay)
            portions.extend(portions_for(pay, (2026, month, "1981.00")))
        return compute_ledger(transactions, payments, portions, PERSONS)

    def test_month_balances_match_production(self) -> None:
        ledger = self._ledger()
        expected = {
            1: Decimal("-24.11"),
            2: Decimal("-1758.69"),
            3: Decimal("-175.90"),
        }
        for month, value in expected.items():
            row = month_row(ledger, 2026, month)
            assert signed(row.balance) == value  # Bob (Kew) owes Alice (Ash)
            assert row.balance is not None
            assert row.balance.from_person_id == BOB.id

    def test_year_matches_production(self) -> None:
        year = self._ledger().years[0]
        assert signed(year.charged) == Decimal("3984.30")
        assert signed(year.paid) == Decimal("5943.00")
        assert year.balance is not None
        assert year.balance.amount == Decimal("1958.70")
        assert year.balance.from_person_id == BOB.id  # Kew owes Ash

    def test_catch_up_lump_zeroes_the_swung_months(self) -> None:
        """The planned Jan-Mar blanket lump brings every residual to zero."""
        ledger = self._ledger()
        covered = [(2026, 1), (2026, 2), (2026, 3)]
        plans = plan_portions(ledger.months, Decimal("1958.70"), BOB.id, covered)
        assert [(p.year, p.month, p.amount) for p in plans] == [
            (2026, 1, Decimal("24.11")),
            (2026, 2, Decimal("1758.69")),
            (2026, 3, Decimal("175.90")),
        ]
        lump = payment(
            "1958.70", from_person=BOB.id, settled=datetime(2026, 5, 1, tzinfo=UTC)
        )
        transactions = [
            month_debt(int(label[:4]), int(label[5:7]), amount)
            for label, amount in self.charges
        ]
        payments = []
        portions: list[SettlementPortion] = []
        for month in (1, 2, 3):
            pay = payment("1981.00", settled=datetime(2026, 4, 26, tzinfo=UTC))
            payments.append(pay)
            portions.extend(portions_for(pay, (2026, month, "1981.00")))
        payments.append(lump)
        portions.extend(
            make_settlement_portion(
                settlement_id=lump.id, year=p.year, month=p.month, amount=p.amount
            )
            for p in plans
        )
        after = compute_ledger(transactions, payments, portions, PERSONS)
        assert after.outstanding is None
        assert all(m.status is MonthSettlementStatus.SETTLED for m in after.months)
        year = after.years[0]
        assert year.balance is None
