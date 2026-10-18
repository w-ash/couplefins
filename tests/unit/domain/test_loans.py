"""Loan balances from the statement and the linked payments since
(US-HOUSE-12): which rows count, how each payment splits, and how the
splits add up to the balance."""

from datetime import date, timedelta
from decimal import Decimal

import attrs
import pytest

from src.domain.date_math import add_months
from src.domain.entities.loan import Loan, slugify
from src.domain.entities.transaction import Transaction
from src.domain.house import OwnerAmount
from src.domain.loans import (
    compute_loan_balance,
    linked_payments,
    loan_figures,
    loan_tag,
    next_due_date,
    owner_payment_parts,
    scheduled_due_dates,
)
from tests.fixtures.factories import (
    ALICE,
    BOB,
    COUPLE_IDS,
    make_loan,
    make_obligation,
    make_transaction,
)

STATEMENT_DAY = date(2026, 1, 1)
MORTGAGE = make_loan(
    name="Mortgage",
    kind="amortizing",
    annual_rate=Decimal("6.000"),
    payment=Decimal("1798.65"),
    statement_balance=Decimal("300000.00"),
    statement_balance_as_of=STATEMENT_DAY,
)
BRIDGE = make_loan(
    name="Bridge loan",
    kind="interest_only",
    principal=Decimal("40000.00"),
    annual_rate=Decimal("8.500"),
    payment=Decimal("283.33"),
    term_months=12,
    statement_balance=Decimal("40000.00"),
    statement_balance_as_of=STATEMENT_DAY,
)


def _payment(
    loan: Loan, amount: str, day: date = date(2026, 2, 1), *tags: str, **fields: object
) -> Transaction:
    """A row tagged with the loan, paid by Alice and split 50/50 unless
    `fields` say otherwise. `amount` is signed."""
    row = make_transaction(
        date=day,
        amount=Decimal(amount),
        tags=(loan_tag(loan), *tags),
        payer_person_id=ALICE.id,
    )
    return attrs.evolve(row, **fields)


class TestSlug:
    @pytest.mark.parametrize(
        ("name", "slug"),
        [
            ("Mortgage", "mortgage"),
            ("Short-term loan (2026)", "short-term-loan-2026"),
            ("  Crédit  Agricole ", "credit-agricole"),
            ("HELOC #2", "heloc-2"),
            ("!!!", ""),
        ],
    )
    def test_a_slug_is_the_names_words_in_lowercase_ascii(
        self, name: str, slug: str
    ) -> None:
        assert slugify(name) == slug

    def test_the_slug_is_stable_and_names_the_tag(self) -> None:
        assert slugify("Mortgage") == slugify("Mortgage")
        assert loan_tag(MORTGAGE) == "loan:mortgage"

    def test_names_that_differ_only_in_case_or_punctuation_share_a_slug(
        self,
    ) -> None:
        """So the use case's uniqueness check refuses the second."""
        assert slugify("Mortgage!") == slugify("mortgage") == "mortgage"


class TestLoanEntity:
    @pytest.mark.parametrize(
        "change",
        [
            {"name": " "},
            {"lender": ""},
            {"principal": Decimal(0)},
            {"payment": Decimal(-1)},
            {"annual_rate": Decimal("-0.1")},
            {"statement_balance": Decimal(-1)},
            {"term_months": 0},
            {"slug": ""},  # a name with no letter or digit
            {"slug": "Mortgage"},
            {"slug": "mort--gage"},
            {"replaced_by_loan_id": BRIDGE.id},  # replaced, but not closed
        ],
    )
    def test_out_of_range_terms_are_rejected(self, change: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            attrs.evolve(MORTGAGE, **change)

    def test_a_loan_can_close_before_its_first_due_date(self) -> None:
        """A bridge loan is often paid off before its first payment."""
        closed = attrs.evolve(
            BRIDGE, closed_on=BRIDGE.first_due_on - timedelta(days=20)
        )

        assert not closed.is_open

    def test_a_loan_cannot_replace_itself(self) -> None:
        with pytest.raises(ValueError, match="itself"):
            attrs.evolve(
                MORTGAGE, closed_on=date(2026, 3, 1), replaced_by_loan_id=MORTGAGE.id
            )

    def test_a_zero_rate_loan_is_open_until_closed(self) -> None:
        free = attrs.evolve(MORTGAGE, annual_rate=Decimal(0))

        assert free.is_open
        assert not attrs.evolve(free, closed_on=date(2026, 2, 1)).is_open


class TestAmortizingBalance:
    def test_each_payment_pays_the_months_interest_first(self) -> None:
        rows = [
            _payment(MORTGAGE, "-1798.65", date(2026, 3, 1)),
            _payment(MORTGAGE, "-1798.65", date(2026, 2, 1)),
        ]

        result = compute_loan_balance(MORTGAGE, rows)

        assert [
            (p.date, p.interest, p.principal, p.balance_after) for p in result.payments
        ] == [
            (
                date(2026, 2, 1),
                Decimal("1500.00"),
                Decimal("298.65"),
                Decimal("299701.35"),
            ),
            # 299,701.35 x 6% / 12 = 1,498.50675, to the cent half up.
            (
                date(2026, 3, 1),
                Decimal("1498.51"),
                Decimal("300.14"),
                Decimal("299401.21"),
            ),
        ]
        assert result.balance == Decimal("299401.21")

    def test_interest_and_principal_add_up_to_the_payments(self) -> None:
        rows = [
            _payment(MORTGAGE, amount, add_months(date(2026, 2, 1), n))
            for n, amount in enumerate(["-1798.65", "-2500.00", "-1798.65", "-100.00"])
        ]

        result = compute_loan_balance(MORTGAGE, rows)

        paid = sum((abs(tx.amount) for tx in rows), Decimal(0))
        assert result.interest_paid + result.principal_paid == paid
        assert result.balance == MORTGAGE.statement_balance - result.principal_paid
        assert all(p.interest + p.principal == p.amount for p in result.payments)

    def test_a_principal_tagged_payment_is_all_principal(self) -> None:
        """An extra principal payment mid-month pays no interest, so the
        balance matches the servicer's next statement."""
        rows = [
            _payment(MORTGAGE, "-1798.65", date(2026, 2, 1)),
            _payment(MORTGAGE, "-5000.00", date(2026, 2, 15), "share:loan-principal"),
            _payment(MORTGAGE, "-1798.65", date(2026, 3, 1)),
        ]

        result = compute_loan_balance(MORTGAGE, rows)

        assert [(p.interest, p.principal) for p in result.payments] == [
            (Decimal("1500.00"), Decimal("298.65")),
            (Decimal(0), Decimal("5000.00")),
            # 294,701.35 x 6% / 12 = 1,473.50675, to the cent half up.
            (Decimal("1473.51"), Decimal("325.14")),
        ]
        assert result.balance == Decimal("294376.21")

    def test_a_payment_under_the_interest_is_all_interest(self) -> None:
        result = compute_loan_balance(MORTGAGE, [_payment(MORTGAGE, "-100.00")])

        [split] = result.payments
        assert (split.interest, split.principal) == (Decimal("100.00"), Decimal(0))
        assert result.balance == MORTGAGE.statement_balance

    def test_no_interest_accrues_on_a_balance_paid_off(self) -> None:
        small = attrs.evolve(MORTGAGE, statement_balance=Decimal("1000.00"))
        rows = [
            _payment(small, "-1005.00", date(2026, 2, 1)),
            _payment(small, "-10.00", date(2026, 3, 1)),
        ]

        result = compute_loan_balance(small, rows)

        assert [p.interest for p in result.payments] == [Decimal("5.00"), Decimal(0)]
        assert result.balance == Decimal("-10.00")


class TestInterestOnlyBalance:
    def test_only_a_principal_tagged_payment_reduces_the_balance(self) -> None:
        rows = [
            _payment(BRIDGE, "-283.33", date(2026, 2, 1), "share:loan-interest"),
            _payment(BRIDGE, "-283.33", date(2026, 3, 1)),
            _payment(BRIDGE, "-5000.00", date(2026, 3, 15), "share:loan-principal"),
        ]

        result = compute_loan_balance(BRIDGE, rows)

        assert [p.principal for p in result.payments] == [
            Decimal(0),
            Decimal(0),
            Decimal("5000.00"),
        ]
        assert result.balance == Decimal("35000.00")
        assert result.interest_paid == Decimal("566.66")
        assert result.interest_paid + result.principal_paid == Decimal("5566.66")


class TestWhichRowsCount:
    def test_rows_on_or_before_the_statement_date_never_count(self) -> None:
        rows = [
            _payment(MORTGAGE, "-1798.65", STATEMENT_DAY),
            _payment(MORTGAGE, "-1798.65", date(2025, 12, 1)),
        ]

        result = compute_loan_balance(MORTGAGE, rows)

        assert result.payments == ()
        assert result.balance == MORTGAGE.statement_balance

    def test_a_new_statement_re_anchors_the_balance(self) -> None:
        rows = [
            _payment(MORTGAGE, "-1798.65", date(2026, 2, 1)),
            _payment(MORTGAGE, "-1798.65", date(2026, 3, 1)),
        ]
        anchored = attrs.evolve(
            MORTGAGE,
            statement_balance=Decimal("299701.35"),
            statement_balance_as_of=date(2026, 2, 15),
        )

        assert compute_loan_balance(anchored, rows).balance == Decimal("299401.21")

    def test_money_in_and_other_loans_rows_are_ignored(self) -> None:
        refund = _payment(MORTGAGE, "50.00")
        other = _payment(BRIDGE, "-283.33", date(2026, 2, 1), "share:loan-principal")
        untagged = make_transaction(amount=Decimal("-1798.65"), date=date(2026, 2, 1))

        assert compute_loan_balance(MORTGAGE, [refund, other, untagged]).payments == ()
        assert linked_payments(MORTGAGE, [refund, other, untagged]) == []

    def test_payments_of_the_same_day_order_by_id(self) -> None:
        rows = [_payment(MORTGAGE, "-900.00") for _ in range(3)]

        ordered = linked_payments(MORTGAGE, rows)

        assert ordered == sorted(rows, key=lambda tx: tx.id)


class TestOwnerParts:
    def test_without_a_payment_the_owners_split_50_50(self) -> None:
        assert owner_payment_parts(MORTGAGE, [], COUPLE_IDS) == (
            OwnerAmount(ALICE.id, Decimal("899.33")),
            OwnerAmount(BOB.id, Decimal("899.32")),
        )

    def test_the_parts_follow_the_most_recent_payments_shares(self) -> None:
        joint = make_transaction(
            joint=True, amount=Decimal("-1798.65"), date=date(2026, 3, 1)
        )
        rows = [
            _payment(MORTGAGE, "-1798.65", date(2026, 2, 1), payer_percentage=100),
            attrs.evolve(
                joint,
                tags=(loan_tag(MORTGAGE),),
                owner_shares={ALICE.id: 40, BOB.id: 60},
            ),
        ]

        parts = owner_payment_parts(MORTGAGE, rows, COUPLE_IDS)

        assert parts == (
            OwnerAmount(ALICE.id, Decimal("719.46")),
            OwnerAmount(BOB.id, Decimal("1079.19")),
        )
        assert sum((p.amount for p in parts), Decimal(0)) == MORTGAGE.payment

    def test_a_payer_who_keeps_it_in_full_pays_the_whole_part(self) -> None:
        rows = [
            _payment(MORTGAGE, "-1798.65", payer_person_id=BOB.id, payer_percentage=100)
        ]

        assert owner_payment_parts(MORTGAGE, rows, COUPLE_IDS) == (
            OwnerAmount(ALICE.id, Decimal(0)),
            OwnerAmount(BOB.id, Decimal("1798.65")),
        )


class TestSchedule:
    def test_a_day_past_the_months_end_clamps_to_its_last_day(self) -> None:
        loan = attrs.evolve(MORTGAGE, first_due_on=date(2026, 1, 31), term_months=4)

        assert list(scheduled_due_dates(loan)) == [
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
            date(2026, 4, 30),
        ]

    def test_a_loan_without_a_term_has_no_last_date(self) -> None:
        loan = attrs.evolve(MORTGAGE, term_months=None)
        dates = scheduled_due_dates(loan)

        assert [next(dates) for _ in range(30)][-1] == date(2028, 7, 1)


class TestNextDue:
    AS_OF = date(2026, 5, 10)

    def test_the_earliest_unpaid_payment_comes_first_even_when_late(self) -> None:
        obligations = [
            make_obligation(
                kind="loan_payment", loan_id=MORTGAGE.id, due_on=date(2026, 6, 1)
            ),
            make_obligation(
                kind="loan_payment", loan_id=MORTGAGE.id, due_on=date(2026, 4, 1)
            ),
            make_obligation(due_on=date(2026, 3, 1)),  # another kind
        ]

        assert next_due_date(MORTGAGE, obligations, self.AS_OF) == date(2026, 4, 1)

    def test_without_one_the_next_scheduled_date_from_the_months_first_day(
        self,
    ) -> None:
        """On the 10th, a payment due on the 1st with no obligation yet is
        still next."""
        assert next_due_date(MORTGAGE, [], self.AS_OF) == date(2026, 5, 1)
        assert next_due_date(MORTGAGE, [], date(2026, 6, 1)) == date(2026, 6, 1)

    def test_a_month_paid_early_is_skipped(self) -> None:
        paid_june = make_obligation(
            kind="loan_payment",
            loan_id=MORTGAGE.id,
            due_on=date(2026, 6, 1),
            paid_by_transaction_id=make_transaction().id,
        )

        assert next_due_date(MORTGAGE, [paid_june], self.AS_OF) == date(2026, 7, 1)

    def test_nothing_is_next_after_the_term_or_once_closed(self) -> None:
        late = make_obligation(
            kind="loan_payment", loan_id=MORTGAGE.id, due_on=date(2026, 4, 1)
        )
        closed = attrs.evolve(MORTGAGE, closed_on=date(2026, 4, 30))

        assert next_due_date(BRIDGE, [], date(2028, 1, 1)) is None
        assert next_due_date(closed, [late], self.AS_OF) is None


class TestFigures:
    def test_an_open_loan_shows_its_balance_and_next_payment(self) -> None:
        rows = [_payment(MORTGAGE, "-1798.65", date(2026, 2, 1))]

        [figures] = loan_figures([MORTGAGE], rows, [], COUPLE_IDS, date(2026, 3, 10))

        assert (figures.balance, figures.next_due) == (
            Decimal("299701.35"),
            date(2026, 3, 1),
        )
        assert (figures.lender, figures.principal, figures.rate_percent) == (
            "Example Bank",
            Decimal("300000.00"),
            Decimal("6.000"),
        )
        assert (figures.closed_on, figures.replaced_by_loan_id) == (None, None)
        assert sum((p.amount for p in figures.owner_parts), Decimal(0)) == (
            MORTGAGE.payment
        )

    def test_a_past_loan_keeps_its_closing_and_replacement(self) -> None:
        closed = attrs.evolve(
            BRIDGE, closed_on=date(2026, 3, 31), replaced_by_loan_id=MORTGAGE.id
        )
        payoff = _payment(
            closed, "-40000.00", date(2026, 3, 31), "share:loan-principal"
        )

        [figures] = loan_figures([closed], [payoff], [], COUPLE_IDS, date(2026, 4, 1))

        assert (figures.balance, figures.closed_on, figures.replaced_by_loan_id) == (
            Decimal(0),
            date(2026, 3, 31),
            MORTGAGE.id,
        )
        assert figures.next_due is None

    def test_each_loan_reads_only_its_own_rows_and_obligations(self) -> None:
        rows = [
            _payment(MORTGAGE, "-1798.65", date(2026, 2, 1)),
            _payment(BRIDGE, "-5000.00", date(2026, 2, 1), "share:loan-principal"),
            make_transaction(amount=Decimal("-75.00"), tags=("share:repair",)),
        ]
        bridge_due = make_obligation(
            kind="loan_payment", loan_id=BRIDGE.id, due_on=date(2026, 2, 1)
        )

        mortgage, bridge = loan_figures(
            [MORTGAGE, BRIDGE], rows, [bridge_due], COUPLE_IDS, date(2026, 3, 10)
        )

        assert (mortgage.balance, mortgage.next_due) == (
            Decimal("299701.35"),
            date(2026, 3, 1),
        )
        assert (bridge.balance, bridge.next_due) == (
            Decimal("35000.00"),
            date(2026, 2, 1),
        )
