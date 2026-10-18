"""The House payload: the example is internally consistent, and recent
activity is real once a joint account exists.

The page renders these figures without arithmetic, so every total, percent,
and difference must already agree with the figures it summarizes.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import attrs
import pytest

from src.application.use_cases._shared.house_example import (
    EXAMPLE_HOUSE,
    example_house,
)
from src.application.use_cases.get_house import (
    HOUSE_SECTIONS,
    GetHouseCommand,
    GetHouseResult,
    GetHouseUseCase,
)
from src.domain.constants import UNASSIGNED_POT
from src.domain.entities.transaction import Transaction
from src.domain.house import (
    ActivityRow,
    HouseFigures,
    HousePerson,
    OwnerAmount,
    OwnerDeposits,
    OwnerShare,
)
from tests.fixtures.factories import (
    ALICE,
    BOB,
    make_co_owned_asset,
    make_joint_account,
    make_share_transaction,
    make_transaction,
    make_transfer_group,
)
from tests.fixtures.mocks import make_mock_uow

COUPLE = (HousePerson(ALICE.id, "Alice"), HousePerson(BOB.id, "Bob"))


def _sum(amounts: Iterable[OwnerAmount]) -> Decimal:
    return sum((a.amount for a in amounts), Decimal(0))


@pytest.fixture(params=["served", "for_the_couple"])
async def figures(request: pytest.FixtureRequest) -> HouseFigures:
    """The example as served before any joint account exists, and as
    re-keyed to the couple once one does."""
    if request.param == "for_the_couple":
        return example_house(ALICE.id, BOB.id)
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
            figures.set_aside.owners,
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
        set_aside = figures.set_aside
        for bucket in set_aside.buckets:
            bank = bucket.bank_balance
            expected = None if bank is None else bank - bucket.balance
            assert bucket.difference == expected, bucket.name
        assert set_aside.bank_balance is not None
        assert set_aside.difference == set_aside.bank_balance - set_aside.total

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


def test_the_couples_example_keys_every_owner_on_the_couple() -> None:
    house = example_house(ALICE.id, BOB.id)

    assert house.persons == COUPLE
    assert house.put_in.total == EXAMPLE_HOUSE.put_in.total
    assert [row.person_id for row in house.recent_activity if row.person_id] == [
        ALICE.id,
        BOB.id,
        ALICE.id,
    ]


class TestRecentActivity:
    """US-HOUSE-7: the joint accounts' latest rows, real once a joint
    account exists."""

    JOINT = make_joint_account("Joint Checking")

    @staticmethod
    async def _house(rows: list[Transaction]) -> GetHouseResult:
        uow = make_mock_uow()
        transfer, card_payment = make_transfer_group()
        uow.persons.get_all.return_value = [ALICE, BOB]
        uow.category_groups.get_all.return_value = [transfer]
        uow.categories.get_all.return_value = [card_payment]
        uow.accounts.get_all.return_value = [TestRecentActivity.JOINT]
        uow.transactions.get_by_account_ids.return_value = rows
        return await GetHouseUseCase().execute(GetHouseCommand(), uow)

    @staticmethod
    def _row(**overrides: object) -> Transaction:
        return attrs.evolve(
            make_transaction(joint=True, account=TestRecentActivity.JOINT.name),
            **overrides,
        )

    @staticmethod
    def _newest_first(rows: list[Transaction]) -> list[Transaction]:
        """Date the rows a day apart, so the activity lists them in order."""
        return [
            attrs.evolve(tx, date=date(2026, 1, 28 - n)) for n, tx in enumerate(rows)
        ]

    async def test_the_section_is_real_and_the_rest_still_example(self) -> None:
        result = await self._house([])

        assert result.example_sections == HOUSE_SECTIONS - {
            "recent_activity",
            "set_aside",
        }
        assert result.figures.recent_activity == ()
        assert result.figures.persons == COUPLE

    async def test_every_section_is_example_without_a_joint_account(self) -> None:
        result = await GetHouseUseCase().execute(GetHouseCommand(), make_mock_uow())

        assert result.example_sections == HOUSE_SECTIONS
        assert result.figures == EXAMPLE_HOUSE

    def test_the_sections_are_every_figure_but_the_couple_and_date(self) -> None:
        assert {
            "put_in",
            "shares",
            "loans",
            "upcoming",
            "set_aside",
            "recent_activity",
        } == HOUSE_SECTIONS

    async def test_kind_follows_category_sign_and_depositor(self) -> None:
        rows = [
            self._row(amount=Decimal("-80.00"), category="Groceries"),
            self._row(amount=Decimal("25.00"), category="Groceries"),
            self._row(
                amount=Decimal("1600.00"),
                category="Deposits",
                depositor_person_id=ALICE.id,
            ),
            self._row(amount=Decimal("-500.00"), category="Credit Card Payment"),
        ]

        result = await self._house(self._newest_first(rows))

        assert [r.kind for r in result.figures.recent_activity] == [
            "payment",
            "refund",
            "deposit",
            "transfer",
        ]
        assert [r.person_id for r in result.figures.recent_activity] == [
            None,
            None,
            ALICE.id,
            None,
        ]

    async def test_a_transfer_naming_its_depositor_is_their_deposit(self) -> None:
        """Depositor first: money in that names a depositor is a deposit,
        and the depositor's alone, even in a transfer-kind category."""
        rows = [
            self._row(
                amount=Decimal("1500.00"),
                category="Credit Card Payment",
                depositor_person_id=BOB.id,
            ),
            self._row(amount=Decimal("1500.00"), category="Credit Card Payment"),
        ]

        result = await self._house(self._newest_first(rows))

        deposit, transfer = result.figures.recent_activity
        assert (deposit.kind, deposit.person_id) == ("deposit", BOB.id)
        assert deposit.shares == (
            OwnerAmount(ALICE.id, Decimal("0.00")),
            OwnerAmount(BOB.id, Decimal("1500.00")),
        )
        assert (transfer.kind, transfer.shares) == ("transfer", ())

    async def test_shares_follow_the_owner_shares_and_skip_transfers(self) -> None:
        rows = [
            self._row(amount=Decimal("-100.00")),
            self._row(
                amount=Decimal("-100.00"), owner_shares={ALICE.id: 60, BOB.id: 40}
            ),
            self._row(amount=Decimal("-100.00"), category="Credit Card Payment"),
        ]

        result = await self._house(self._newest_first(rows))

        assert [r.shares for r in result.figures.recent_activity] == [
            (
                OwnerAmount(ALICE.id, Decimal("50.00")),
                OwnerAmount(BOB.id, Decimal("50.00")),
            ),
            (
                OwnerAmount(ALICE.id, Decimal("60.00")),
                OwnerAmount(BOB.id, Decimal("40.00")),
            ),
            (),
        ]

    async def test_budget_line_is_the_first_line_tag(self) -> None:
        rows = [
            self._row(tags=("shared", "line:repair", "line:renovation")),
            self._row(tags=("shared",)),
        ]

        result = await self._house(self._newest_first(rows))

        assert [r.budget_line for r in result.figures.recent_activity] == [
            "repair",
            None,
        ]

    async def test_lists_the_newest_twenty_rows_with_their_account(self) -> None:
        rows = [self._row(date=date(2026, 1, day)) for day in range(1, 26)]
        same_day = [self._row(date=date(2026, 1, 26)) for _ in range(2)]

        result = await self._house([*rows[::2], *same_day, *rows[1::2]])

        activity: tuple[ActivityRow, ...] = result.figures.recent_activity
        assert [r.id for r in activity] == [
            *sorted(tx.id for tx in same_day),
            *(tx.id for tx in reversed(rows[-18:])),
        ]
        assert {r.account_name for r in activity} == {"Joint Checking"}


class TestJointFunds:
    """The set-aside pots and each owner's unspent deposits, from every row
    of the joint accounts, once one exists."""

    JOINT = make_joint_account("Joint Checking")

    @staticmethod
    async def _house(rows: list[Transaction]) -> GetHouseResult:
        uow = make_mock_uow()
        transfer, card_payment = make_transfer_group()
        uow.persons.get_all.return_value = [ALICE, BOB]
        uow.category_groups.get_all.return_value = [transfer]
        uow.categories.get_all.return_value = [card_payment]
        uow.accounts.get_all.return_value = [TestJointFunds.JOINT]
        uow.transactions.get_by_account_ids.return_value = rows
        result = await GetHouseUseCase().execute(GetHouseCommand(), uow)
        uow.transactions.get_by_account_ids.assert_awaited_once_with([
            TestJointFunds.JOINT.id
        ])
        return result

    @staticmethod
    def _row(amount: str, *tags: str, **overrides: object) -> Transaction:
        return attrs.evolve(
            make_transaction(
                joint=True,
                account=TestJointFunds.JOINT.name,
                amount=Decimal(amount),
                tags=tags,
            ),
            **overrides,
        )

    ROWS = (
        ("1000.00", ("pot:bills",), {"depositor_person_id": ALICE.id}),
        ("600.00", ("pot:renovation",), {"depositor_person_id": BOB.id}),
        ("-300.00", ("pot:bills", "line:mortgage"), {}),
        ("-100.00", ("pot:bills",), {"category": "Credit Card Payment"}),
        ("100.00", ("pot:renovation",), {"category": "Credit Card Payment"}),
        ("-20.00", (), {}),
    )

    async def _month(self) -> GetHouseResult:
        return await self._house([
            self._row(amount, *tags, **overrides)
            for amount, tags, overrides in self.ROWS
        ])

    async def test_set_aside_lists_each_pot_with_unassigned_last(self) -> None:
        set_aside = (await self._month()).figures.set_aside

        assert [(b.name, b.balance, b.is_unassigned) for b in set_aside.buckets] == [
            ("bills", Decimal("600.00"), False),
            ("renovation", Decimal("700.00"), False),
            (UNASSIGNED_POT, Decimal("-20.00"), True),
        ]
        assert set_aside.total == Decimal("1280.00")
        assert all(
            (b.bank_balance, b.bank_balance_as_of, b.difference) == (None, None, None)
            for b in set_aside.buckets
        )

    async def test_set_aside_holds_each_owners_deposits_and_put_in_stays_example(
        self,
    ) -> None:
        result = await self._month()

        # Spending 300 + 20 at 50/50; the transfer legs are no payment.
        assert result.figures.set_aside.owners == (
            OwnerDeposits(
                ALICE.id,
                Decimal("1000.00"),
                Decimal(0),
                Decimal("160.00"),
                Decimal("840.00"),
            ),
            OwnerDeposits(
                BOB.id,
                Decimal("600.00"),
                Decimal(0),
                Decimal("160.00"),
                Decimal("440.00"),
            ),
        )
        assert result.figures.put_in == example_house(ALICE.id, BOB.id).put_in
        assert "put_in" in result.example_sections
        assert "set_aside" not in result.example_sections

    async def test_no_joint_rows_no_pots(self) -> None:
        set_aside = (await self._house([])).figures.set_aside

        assert set_aside.buckets == ()
        assert set_aside.total == 0
        assert [o.unspent for o in set_aside.owners] == [0, 0]
        assert (set_aside.bank_balance, set_aside.difference) == (None, None)


class TestOwnerShares:
    """US-HOUSE-2, -3, -10: once the asset exists, Put in, Shares, and Set
    aside are real, from the rows dated through the as-of date."""

    AS_OF = date(2026, 4, 10)
    ASSET = make_co_owned_asset(
        bank_balance=Decimal("950.00"), bank_balance_as_of=date(2026, 4, 1)
    )
    JOINT = make_joint_account("Joint Checking")
    ROWS = (
        make_share_transaction("closing", Decimal("-3000.00"), date=date(2025, 11, 3)),
        make_share_transaction(
            "insurance",
            Decimal("-300.00"),
            date=date(2026, 2, 27),
            payer_person_id=BOB.id,
            payer_percentage=100,
            tags=("s100",),
        ),
        # After the as-of date, in its month: in no section yet.
        make_share_transaction("closing", Decimal("-999.00"), date=date(2026, 4, 20)),
    )

    @staticmethod
    async def _house(
        rows: Iterable[Transaction] = ROWS,
        joint_rows: Iterable[Transaction] | None = None,
    ) -> GetHouseResult:
        uow = make_mock_uow()
        transfer, card_payment = make_transfer_group()
        uow.persons.get_all.return_value = [ALICE, BOB]
        uow.category_groups.get_all.return_value = [transfer]
        uow.categories.get_all.return_value = [card_payment]
        uow.co_owned_assets.get_current.return_value = TestOwnerShares.ASSET
        uow.transactions.get_by_tag_prefix.return_value = list(rows)
        joint_ids = []
        if joint_rows is not None:
            uow.accounts.get_all.return_value = [TestOwnerShares.JOINT]
            uow.transactions.get_by_account_ids.return_value = list(joint_rows)
            joint_ids = [TestOwnerShares.JOINT.id]
        result = await GetHouseUseCase().execute(
            GetHouseCommand(as_of=TestOwnerShares.AS_OF), uow
        )
        uow.transactions.get_by_tag_prefix.assert_awaited_once_with(
            "share:", excluding_account_ids=joint_ids
        )
        return result

    @staticmethod
    def _joint_row(amount: str, *tags: str, **overrides: object) -> Transaction:
        return attrs.evolve(
            make_transaction(
                joint=True,
                account=TestOwnerShares.JOINT.name,
                amount=Decimal(amount),
                tags=tags,
            ),
            **overrides,
        )

    async def test_put_in_shares_and_set_aside_are_real_once_the_asset_exists(
        self,
    ) -> None:
        result = await self._house()

        assert result.example_sections == HOUSE_SECTIONS - {
            "put_in",
            "shares",
            "set_aside",
        }
        assert result.asset == self.ASSET
        assert result.figures.as_of == self.AS_OF
        assert result.figures.persons == COUPLE

    async def test_put_in_holds_each_owners_credits_by_kind(self) -> None:
        put_in = (await self._house()).figures.put_in

        assert [(k.kind, k.amounts, k.total) for k in put_in.kinds] == [
            (
                "closing",
                (
                    OwnerAmount(ALICE.id, Decimal("1500.00")),
                    OwnerAmount(BOB.id, Decimal("1500.00")),
                ),
                Decimal("3000.00"),
            ),
            (
                "insurance",
                (
                    OwnerAmount(ALICE.id, Decimal(0)),
                    OwnerAmount(BOB.id, Decimal("300.00")),
                ),
                Decimal("300.00"),
            ),
        ]
        assert put_in.total == Decimal("3300.00")

    async def test_the_history_runs_from_the_first_credit_through_as_of(
        self,
    ) -> None:
        shares = (await self._house()).figures.shares

        assert [(p.year, p.month) for p in shares.history] == [
            (2025, 11),
            (2025, 12),
            (2026, 1),
            (2026, 2),
            (2026, 3),
            (2026, 4),
        ]
        assert shares.history[-1].owners == shares.now
        assert [(s.capital, s.percent) for s in shares.now] == [
            (Decimal("1500.00"), Decimal("45.5")),
            (Decimal("1800.00"), Decimal("54.5")),
        ]

    async def test_without_credits_the_shares_are_zero_now(self) -> None:
        figures = (await self._house(rows=[])).figures

        assert figures.put_in.kinds == ()
        assert [(p.year, p.month) for p in figures.shares.history] == [(2026, 4)]
        assert [(s.capital, s.percent) for s in figures.shares.now] == [
            (Decimal(0), Decimal(0)),
            (Decimal(0), Decimal(0)),
        ]

    async def test_unspent_deposits_come_from_the_joint_funds(self) -> None:
        deposit = self._joint_row("1000.00", depositor_person_id=ALICE.id)
        payment = self._joint_row("-200.00")

        result = await self._house(joint_rows=[deposit, payment])

        figures = result.figures
        assert figures.put_in.unspent_deposits == (
            OwnerAmount(ALICE.id, Decimal("900.00")),
            OwnerAmount(BOB.id, Decimal("-100.00")),
        )
        assert [o.unspent for o in figures.set_aside.owners] == [
            a.amount for a in figures.put_in.unspent_deposits
        ]
        assert result.example_sections == {"loans", "upcoming"}

    async def test_without_a_joint_account_set_aside_is_real_and_empty(
        self,
    ) -> None:
        figures = (await self._house()).figures

        assert figures.set_aside.buckets == ()
        assert [o.unspent for o in figures.set_aside.owners] == [0, 0]
        assert figures.put_in.unspent_deposits == (
            OwnerAmount(ALICE.id, Decimal(0)),
            OwnerAmount(BOB.id, Decimal(0)),
        )

    async def test_the_assets_bank_balance_stands_beside_the_pots(self) -> None:
        rows = [
            self._joint_row("1000.00", "pot:bills", depositor_person_id=ALICE.id),
            self._joint_row("-20.00"),
        ]

        set_aside = (await self._house(joint_rows=rows)).figures.set_aside

        assert set_aside.total == Decimal("980.00")
        assert (set_aside.bank_balance, set_aside.bank_balance_as_of) == (
            Decimal("950.00"),
            date(2026, 4, 1),
        )
        assert set_aside.difference == Decimal("-30.00")
        assert all(b.bank_balance is None for b in set_aside.buckets)

    async def test_a_joint_share_row_is_read_once_and_credited_once(self) -> None:
        """The share rows outside the joint accounts are read apart; the
        joint ones come from the joint rows."""
        premium = self._joint_row("-400.00", "share:insurance")

        figures = (await self._house(rows=[], joint_rows=[premium])).figures

        assert [s.capital for s in figures.shares.now] == [
            Decimal("200.00"),
            Decimal("200.00"),
        ]

    async def test_every_section_counts_the_rows_through_the_as_of_date(
        self,
    ) -> None:
        on_time = self._joint_row("-100.00", "share:repair", date=self.AS_OF)
        later = self._joint_row("-700.00", "share:repair", date=date(2026, 4, 11))

        figures = (await self._house(rows=[], joint_rows=[on_time, later])).figures

        assert [r.id for r in figures.recent_activity] == [on_time.id]
        assert figures.set_aside.total == Decimal("-100.00")
        assert figures.put_in.kinds == ()  # the on-time repair is under 500
        assert [s.capital for s in figures.shares.now] == [0, 0]
