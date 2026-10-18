"""What comes due (US-HOUSE-13): each obligation's status, the order it is
listed in, the payments generated from a loan, and the rows offered as its
payment."""

from datetime import date, timedelta
from decimal import Decimal

import attrs
import pytest

from src.domain.candidate_ranking import MAX_CANDIDATES
from src.domain.entities.obligation import Obligation
from src.domain.entities.transaction import Transaction
from src.domain.loans import loan_tag
from src.domain.obligations import (
    RECENT_PAID_LIMIT,
    PaymentCandidate,
    find_payment_candidates,
    generate_loan_payment_obligations,
    obligation_figures,
    obligation_status,
    paid_by_others,
    recently_paid,
    upcoming,
)
from tests.fixtures.factories import make_loan, make_obligation, make_transaction

DUE = date(2026, 11, 1)
TAX = make_obligation(amount=Decimal("1200.00"), due_on=DUE)
LOAN = make_loan(first_due_on=date(2026, 1, 31), term_months=None)


def _paid(obligation_due: date) -> Obligation:
    return make_obligation(
        due_on=obligation_due, paid_by_transaction_id=make_transaction().id
    )


class TestObligationEntity:
    @pytest.mark.parametrize(
        "change",
        [
            {"description": "  "},
            {"amount": Decimal(0)},
            {"late_after": DUE - timedelta(days=1)},
            {"kind": "loan_payment"},  # with no loan
            {"loan_id": LOAN.id},  # a property tax naming a loan
        ],
    )
    def test_out_of_range_values_are_rejected(self, change: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            attrs.evolve(TAX, **change)

    def test_a_loan_payment_names_its_loan(self) -> None:
        payment = attrs.evolve(TAX, kind="loan_payment", loan_id=LOAN.id)

        assert payment.loan_id == LOAN.id
        assert not payment.is_paid


class TestStatus:
    def test_without_a_late_date_it_is_late_the_day_after_it_is_due(self) -> None:
        assert obligation_status(TAX, DUE - timedelta(days=1)) == "due"
        assert obligation_status(TAX, DUE) == "due"
        assert obligation_status(TAX, DUE + timedelta(days=1)) == "late"

    def test_with_a_late_date_it_stays_due_through_that_date(self) -> None:
        installment = attrs.evolve(TAX, late_after=date(2026, 12, 10))

        assert obligation_status(installment, date(2026, 12, 10)) == "due"
        assert obligation_status(installment, date(2026, 12, 11)) == "late"

    def test_a_linked_row_makes_it_paid_whenever_it_was_due(self) -> None:
        paid = attrs.evolve(TAX, paid_by_transaction_id=make_transaction().id)

        assert obligation_status(paid, DUE + timedelta(days=90)) == "paid"


class TestLists:
    def test_upcoming_is_the_unpaid_ones_in_due_order(self) -> None:
        later = make_obligation(due_on=date(2027, 1, 15), description="Insurance")
        same_day_b = make_obligation(due_on=DUE, description="B")
        same_day_a = make_obligation(due_on=DUE, description="A")
        late = make_obligation(due_on=date(2026, 9, 1))

        listed = upcoming([later, _paid(DUE), same_day_b, late, same_day_a])

        assert listed == [late, same_day_a, same_day_b, later]

    def test_recently_paid_is_the_newest_ten_by_due_date(self) -> None:
        paid = [_paid(DUE + timedelta(days=n)) for n in range(12)]

        recent = recently_paid([*paid, TAX])

        assert len(recent) == RECENT_PAID_LIMIT
        assert recent == sorted(paid, key=lambda o: o.due_on, reverse=True)[:10]

    def test_figures_carry_the_status_and_the_paying_row(self) -> None:
        row = make_transaction()
        payment = make_obligation(
            kind="loan_payment",
            loan_id=LOAN.id,
            description="Mortgage payment",
            pays_from="bills",
            paid_by_transaction_id=row.id,
        )

        figures = obligation_figures(payment, DUE)

        assert (figures.name, figures.status, figures.due) == (
            "Mortgage payment",
            "paid",
            DUE,
        )
        assert (figures.loan_id, figures.paid_by_transaction_id) == (LOAN.id, row.id)
        assert (figures.pays_from, figures.shortfall) == ("bills", None)


class TestGeneratedPayments:
    TODAY = date(2026, 1, 1)

    def test_the_next_months_come_from_the_schedule_clamped(self) -> None:
        added = generate_loan_payment_obligations(LOAN, [], 3, self.TODAY)

        assert [o.due_on for o in added] == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
        ]
        assert {(o.kind, o.loan_id, o.amount, o.pays_from) for o in added} == {
            ("loan_payment", LOAN.id, LOAN.payment, None)
        }
        assert {o.description for o in added} == {"Mortgage payment"}
        assert {o.asset_id for o in added} == {LOAN.asset_id}
        assert len({o.id for o in added}) == 3
        assert not any(o.is_estimate or o.is_paid for o in added)

    def test_months_after_the_latest_existing_one_and_without_one(self) -> None:
        def existing(day: date) -> Obligation:
            return make_obligation(kind="loan_payment", loan_id=LOAN.id, due_on=day)

        # February was entered on the 15th; March is the next free month.
        have = [existing(date(2026, 1, 31)), existing(date(2026, 2, 15))]
        other_loan = make_obligation(
            kind="loan_payment", loan_id=make_loan().id, due_on=date(2026, 3, 31)
        )

        added = generate_loan_payment_obligations(
            LOAN, [*have, other_loan], 2, self.TODAY
        )

        assert [o.due_on for o in added] == [date(2026, 3, 31), date(2026, 4, 30)]

    def test_no_payment_falls_before_this_month(self) -> None:
        added = generate_loan_payment_obligations(LOAN, [], 2, date(2026, 6, 1))

        assert [o.due_on for o in added] == [date(2026, 6, 30), date(2026, 7, 31)]

    def test_a_payment_due_earlier_this_month_is_still_added(self) -> None:
        """On the 17th, the payment due on the 1st has no obligation yet."""
        on_the_first = attrs.evolve(LOAN, first_due_on=date(2026, 1, 1))

        added = generate_loan_payment_obligations(
            on_the_first, [], 2, date(2026, 6, 17)
        )

        assert [o.due_on for o in added] == [date(2026, 6, 1), date(2026, 7, 1)]

    def test_the_term_caps_how_many_come_back(self) -> None:
        short = attrs.evolve(LOAN, term_months=2)

        added = generate_loan_payment_obligations(short, [], 24, self.TODAY)

        assert len(added) == 2


class TestCandidates:
    @staticmethod
    def _row(amount: str, day: date, *tags: str) -> Transaction:
        return make_transaction(amount=Decimal(amount), date=day, tags=tags)

    @staticmethod
    def _ranked(
        obligation: Obligation,
        rows: list[Transaction],
        obligations: tuple[Obligation, ...] = (),
    ) -> list[PaymentCandidate]:
        return find_payment_candidates(
            obligation, rows, obligations=obligations, loan=None
        )

    def test_the_amount_and_date_add_up_to_the_score(self) -> None:
        """Days 31 to 45 are read but score on the amount alone."""
        exact_on_time = self._row("-1200.00", DUE)
        close_within_a_month = self._row("-1215.00", DUE + timedelta(days=20))
        off_amount_near = self._row("-90.00", DUE + timedelta(days=3))
        dollar_off_late = self._row("-1200.99", DUE + timedelta(days=40))

        ranked = self._ranked(
            TAX,
            [dollar_off_late, off_amount_near, close_within_a_month, exact_on_time],
        )

        assert [(c.transaction, c.score) for c in ranked] == [
            (exact_on_time, 5),
            (close_within_a_month, 4),
            (dollar_off_late, 3),
            (off_amount_near, 2),
        ]

    def test_a_row_with_the_loans_tag_scores_two_more(self) -> None:
        payment = make_obligation(
            kind="loan_payment",
            loan_id=LOAN.id,
            amount=LOAN.payment,
            due_on=DUE,
        )
        tagged = self._row("-50.00", DUE + timedelta(days=40), loan_tag(LOAN))
        untagged = self._row("-50.00", DUE + timedelta(days=40))
        other_loan = self._row("-50.00", DUE + timedelta(days=40), "loan:other")

        ranked = find_payment_candidates(
            payment, [untagged, other_loan, tagged], obligations=[], loan=LOAN
        )

        assert [(c.transaction, c.score) for c in ranked] == [(tagged, 2)]

    def test_a_row_that_pays_another_obligation_is_left_out(self) -> None:
        taken = self._row("-1200.00", DUE)
        free = self._row("-1200.00", DUE + timedelta(days=1))
        other = make_obligation(paid_by_transaction_id=taken.id)
        this_one = attrs.evolve(TAX, paid_by_transaction_id=free.id)

        ranked = self._ranked(this_one, [taken, free], (other, this_one))

        assert [c.transaction for c in ranked] == [free]
        assert paid_by_others(this_one, [other, this_one]) == {taken.id}

    def test_money_in_out_of_window_and_unscored_rows_are_left_out(self) -> None:
        rows = [
            self._row("1200.00", DUE),  # a refund
            self._row("-1200.00", DUE - timedelta(days=15)),  # before the window
            self._row("-1200.00", DUE + timedelta(days=46)),  # after it
            self._row("-50.00", DUE + timedelta(days=31)),  # scores nothing
        ]

        assert self._ranked(TAX, rows) == []

    def test_ties_go_to_the_earlier_row_and_the_list_is_capped(self) -> None:
        rows = [self._row("-1200.00", DUE + timedelta(days=n % 5)) for n in range(25)]

        ranked = self._ranked(TAX, rows)

        assert len(ranked) == MAX_CANDIDATES
        keys = [(c.transaction.date, c.transaction.id) for c in ranked]
        assert keys == sorted(keys)
