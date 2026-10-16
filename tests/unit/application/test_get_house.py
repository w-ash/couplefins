"""The House example payload is internally consistent.

The page renders these figures without arithmetic, so every total, percent,
and difference must already agree with the figures it summarizes.
"""

from collections.abc import Iterable
from decimal import Decimal

import pytest

from src.application.use_cases.get_house import GetHouseCommand, GetHouseUseCase
from src.domain.house import HouseFigures, OwnerAmount, OwnerShare
from tests.fixtures.mocks import make_mock_uow


def _sum(amounts: Iterable[OwnerAmount]) -> Decimal:
    return sum((a.amount for a in amounts), Decimal(0))


@pytest.fixture
async def figures() -> HouseFigures:
    result = await GetHouseUseCase().execute(GetHouseCommand(), make_mock_uow())
    return result.figures


class TestExampleHouse:
    def test_every_owner_list_follows_persons_order(
        self, figures: HouseFigures
    ) -> None:
        ids = [p.id for p in figures.persons]
        owner_lists: list[Iterable[OwnerAmount | OwnerShare]] = [
            figures.put_in.totals,
            figures.put_in.unspent_deposits,
            figures.shares.now,
            *(k.amounts for k in figures.put_in.kinds),
            *(p.owners for p in figures.shares.history),
            *(loan.owner_parts for loan in figures.loans),
            *(row.shares for row in figures.recent_activity),
        ]
        for owners in owner_lists:
            assert [o.person_id for o in owners] == ids

    def test_put_in_totals_add_up(self, figures: HouseFigures) -> None:
        put_in = figures.put_in
        for kind in put_in.kinds:
            assert kind.total == _sum(kind.amounts), kind.kind
        for total in put_in.totals:
            parts = (a for k in put_in.kinds for a in k.amounts)
            assert total.amount == _sum(
                a for a in parts if a.person_id == total.person_id
            )
        assert put_in.total == _sum(put_in.totals)

    def test_percents_sum_to_100_and_history_ends_at_now(
        self, figures: HouseFigures
    ) -> None:
        shares = figures.shares
        for owners in (shares.now, *(p.owners for p in shares.history)):
            assert sum((s.percent for s in owners), Decimal(0)) == 100
        assert shares.history[-1].owners == shares.now

    def test_loan_owner_parts_sum_to_payment(self, figures: HouseFigures) -> None:
        for loan in figures.loans:
            assert _sum(loan.owner_parts) == loan.payment, loan.name

    def test_bucket_difference_is_bank_minus_book(self, figures: HouseFigures) -> None:
        for bucket in figures.set_aside.buckets:
            bank = bucket.bank_balance
            expected = None if bank is None else bank - bucket.balance
            assert bucket.difference == expected, bucket.name

    def test_activity_shares_sum_to_the_absolute_amount(
        self, figures: HouseFigures
    ) -> None:
        for row in figures.recent_activity:
            assert _sum(row.shares) == abs(row.amount), row.id

    def test_one_obligation_falls_short_of_what_its_bucket_has_left(
        self, figures: HouseFigures
    ) -> None:
        balances = {b.name: b.balance for b in figures.set_aside.buckets}
        [short] = [o for o in figures.upcoming if o.shortfall is not None]
        assert short.pays_from is not None
        earlier = figures.upcoming[: figures.upcoming.index(short)]
        left = balances[short.pays_from] - sum(
            (o.amount for o in earlier if o.pays_from == short.pays_from), Decimal(0)
        )
        assert short.shortfall == short.amount - left

    def test_lists_are_in_their_served_order(self, figures: HouseFigures) -> None:
        months = [(p.year, p.month) for p in figures.shares.history]
        dues = [o.due for o in figures.upcoming]
        dates = [row.date for row in figures.recent_activity]
        assert months == sorted(months)
        assert dues == sorted(dues)
        assert dates == sorted(dates, reverse=True)
