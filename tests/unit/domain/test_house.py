import datetime
from decimal import Decimal

from src.domain.house import (
    bucket,
    put_in_section,
    set_aside_section,
    share_percentages,
    shares_section,
    with_shortfalls,
)
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_obligation,
    make_owner_amount,
    make_owner_share,
    make_share_history_point,
)

OWNERS = (ALICE.id, BOB.id)


class TestPutInSection:
    def test_totals_each_kind_each_owner_and_all_owners(self) -> None:
        closing = (
            make_owner_amount(person_id=ALICE.id, amount=Decimal(600)),
            make_owner_amount(person_id=BOB.id, amount=Decimal(400)),
        )
        repair = (
            make_owner_amount(person_id=ALICE.id, amount=Decimal(30)),
            make_owner_amount(person_id=BOB.id, amount=Decimal(20)),
        )
        unspent = (make_owner_amount(person_id=ALICE.id, amount=Decimal(5)),)

        section = put_in_section(
            OWNERS, {"closing": closing, "repair": repair}, unspent
        )

        assert [(k.kind, k.total) for k in section.kinds] == [
            ("closing", Decimal(1000)),
            ("repair", Decimal(50)),
        ]
        assert [(t.person_id, t.amount) for t in section.totals] == [
            (ALICE.id, Decimal(630)),
            (BOB.id, Decimal(420)),
        ]
        assert section.total == Decimal(1050)
        assert section.unspent_deposits == unspent

    def test_an_owner_with_no_contributions_totals_zero_in_owner_order(
        self,
    ) -> None:
        closing = (make_owner_amount(person_id=ALICE.id, amount=Decimal(600)),)

        section = put_in_section((BOB.id, ALICE.id), {"closing": closing}, ())

        assert [(t.person_id, t.amount) for t in section.totals] == [
            (BOB.id, Decimal(0)),
            (ALICE.id, Decimal(600)),
        ]
        assert section.total == Decimal(600)

    def test_no_kinds_totals_zero_for_each_owner(self) -> None:
        section = put_in_section(OWNERS, {}, ())

        assert [(t.person_id, t.amount) for t in section.totals] == [
            (ALICE.id, Decimal(0)),
            (BOB.id, Decimal(0)),
        ]
        assert section.total == Decimal(0)


class TestSharePercentages:
    def test_rounds_to_a_tenth_and_the_last_owner_takes_the_rest(self) -> None:
        shares = share_percentages({ALICE.id: Decimal(1), BOB.id: Decimal(2)})

        assert shares == (
            make_owner_share(
                person_id=ALICE.id, capital=Decimal(1), percent=Decimal("33.3")
            ),
            make_owner_share(
                person_id=BOB.id, capital=Decimal(2), percent=Decimal("66.7")
            ),
        )

    def test_a_half_tenth_rounds_up(self) -> None:
        shares = share_percentages({ALICE.id: Decimal(49), BOB.id: Decimal(351)})

        assert [s.percent for s in shares] == [Decimal("12.3"), Decimal("87.7")]

    def test_zero_capital_gives_zero_percents(self) -> None:
        shares = share_percentages({ALICE.id: Decimal(0), BOB.id: Decimal(0)})

        assert [s.percent for s in shares] == [Decimal(0), Decimal(0)]


class TestSharesSection:
    def test_now_is_the_last_point(self) -> None:
        first = make_share_history_point(
            year=2026,
            month=1,
            owners=share_percentages({ALICE.id: Decimal(50), BOB.id: Decimal(50)}),
        )
        last = make_share_history_point(
            year=2026,
            month=2,
            owners=share_percentages({ALICE.id: Decimal(70), BOB.id: Decimal(30)}),
        )

        section = shares_section((first, last))

        assert section.now == last.owners
        assert section.total_capital == Decimal(100)

    def test_empty_history_has_no_shares(self) -> None:
        section = shares_section(())

        assert section.now == ()
        assert section.total_capital == Decimal(0)


class TestBucket:
    def test_difference_is_bank_minus_book(self) -> None:
        as_of = datetime.date(2026, 9, 30)

        b = bucket("Renovation", Decimal(1000), Decimal(950), as_of)

        assert b.difference == Decimal(-50)
        assert b.bank_balance_as_of == as_of

    def test_no_bank_balance_has_no_difference(self) -> None:
        b = bucket("Repairs reserve", Decimal(1000))

        assert b.bank_balance is None
        assert b.bank_balance_as_of is None
        assert b.difference is None


class TestSetAsideSection:
    def test_total_is_the_sum_of_balances(self) -> None:
        buckets = (bucket("Tax", Decimal(300)), bucket("Repairs", Decimal(200)))

        assert set_aside_section(buckets).total == Decimal(500)


class TestWithShortfalls:
    def test_only_the_later_payment_from_a_bucket_runs_short(self) -> None:
        first = make_obligation(amount=Decimal(300), pays_from="Loans")
        second = make_obligation(amount=Decimal(300), pays_from="Loans")

        result = with_shortfalls((first, second), {"Loans": Decimal(500)})

        assert [o.shortfall for o in result] == [None, Decimal(100)]
        assert [o.id for o in result] == [first.id, second.id]

    def test_a_short_first_payment_leaves_nothing_for_the_next(self) -> None:
        first = make_obligation(amount=Decimal(300), pays_from="Loans")
        second = make_obligation(amount=Decimal(50), pays_from="Loans")

        result = with_shortfalls((first, second), {"Loans": Decimal(100)})

        assert [o.shortfall for o in result] == [Decimal(200), Decimal(50)]

    def test_each_bucket_keeps_its_own_balance(self) -> None:
        loan = make_obligation(amount=Decimal(300), pays_from="Loans")
        tax = make_obligation(amount=Decimal(300), pays_from="Tax")

        result = with_shortfalls(
            (loan, tax), {"Loans": Decimal(300), "Tax": Decimal(300)}
        )

        assert [o.shortfall for o in result] == [None, None]

    def test_no_bucket_or_an_unknown_bucket_gives_no_shortfall(self) -> None:
        unknown = make_obligation(amount=Decimal(300), pays_from="Tax")
        no_bucket = make_obligation(amount=Decimal(300), pays_from=None)

        result = with_shortfalls((unknown, no_bucket), {"Loans": Decimal(0)})

        assert [o.shortfall for o in result] == [None, None]
