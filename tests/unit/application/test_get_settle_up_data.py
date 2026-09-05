from datetime import UTC, date, datetime
from decimal import Decimal

from src.application.use_cases.get_settle_up_data import (
    GetSettleUpDataCommand,
    GetSettleUpDataUseCase,
)
from src.domain.ledger import MonthSettlementStatus
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
    make_reconciliation_period,
    make_settlement,
    make_settlement_portion,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def _setup_uow(
    alice,
    bob,
    *,
    transactions: list | None = None,
    settlements: list | None = None,
    portions: list | None = None,
    categories: list | None = None,
    groups: list | None = None,
    uploads: list | None = None,
):
    """Wire both the ledger fetches (all-time) and the month audit fetches
    from one dataset — mirroring a database where they are the same rows."""
    group = groups[0] if groups else make_category_group()
    category = (categories or [make_category(group_id=group.id)])[0]
    txs = transactions or []

    uow = make_mock_uow()
    uow.persons.get_all.return_value = [alice, bob]
    uow.categories.get_all.return_value = categories or [category]
    uow.category_groups.get_all.return_value = groups or [group]
    # Ledger (all-time) fetches
    uow.transactions.get_all_settlement_relevant.return_value = txs
    uow.settlements.get_all.return_value = settlements or []
    uow.settlement_portions.get_all.return_value = portions or []
    # Month audit fetches — callers pass month-scoped rows via these kwargs
    uow.transactions.get_settlement_relevant_by_date_range.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = (
        uploads or []
    )
    return uow


def _month(result, year: int, month: int):
    return next(m for m in result.months if (m.year, m.month) == (year, month))


def _year(result, year: int):
    return next(y for y in result.years if y.year == year)


class TestGetSettleUpData:
    async def test_returns_month_and_year_balances(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 1, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        settlement = make_settlement(
            amount=Decimal("30.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        portion = make_settlement_portion(
            settlement_id=settlement.id, year=2026, month=1, amount=Decimal("30.00")
        )
        uow = _setup_uow(
            alice,
            bob,
            transactions=[tx],
            settlements=[settlement],
            portions=[portion],
            uploads=[make_upload(person_id=alice.id)],
        )

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.year == 2026
        assert result.month == 1
        jan = _month(result, 2026, 1)
        assert jan.charged is not None
        assert jan.charged.amount == Decimal("50.00")
        assert jan.charged.from_person_id == bob.id
        assert jan.paid is not None
        assert jan.paid.amount == Decimal("30.00")
        assert jan.balance is not None
        assert jan.balance.amount == Decimal("20.00")
        assert jan.balance.from_person_id == bob.id
        assert jan.status is MonthSettlementStatus.PARTIALLY_SETTLED

        year = _year(result, 2026)
        assert year.charged is not None
        assert year.charged.amount == Decimal("50.00")
        assert year.paid is not None
        assert year.paid.amount == Decimal("30.00")
        assert year.balance is not None
        assert year.balance.amount == Decimal("20.00")
        assert year.span == ((2026, 1), (2026, 1))

        assert len(result.settlements) == 1
        entry = result.settlements[0]
        assert [(p.year, p.month, p.amount) for p in entry.application.portions] == [
            (2026, 1, Decimal("30.00"))
        ]
        assert result.is_finalized is False

    async def test_month_row_is_the_drilldown_figure(self) -> None:
        """The month row and its drill-down Summary read the same object —
        the original bug was two computations disagreeing."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 1, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        uow = _setup_uow(alice, bob, transactions=[tx])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        # Exactly one row carries the selected month's figures; there is no
        # second month-scoped balance field to diverge from it.
        rows = [m for m in result.months if (m.year, m.month) == (2026, 1)]
        assert len(rows) == 1
        assert rows[0].balance is not None
        assert rows[0].balance.amount == Decimal("50.00")

    async def test_settled_month_reads_settled(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 1, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        settlement = make_settlement(
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        portion = make_settlement_portion(
            settlement_id=settlement.id, year=2026, month=1, amount=Decimal("50.00")
        )
        uow = _setup_uow(
            alice, bob, transactions=[tx], settlements=[settlement], portions=[portion]
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        jan = _month(result, 2026, 1)
        assert jan.balance is None
        assert jan.status is MonthSettlementStatus.SETTLED
        year = _year(result, 2026)
        assert year.balance is None

    async def test_month_paid_past_charges_swings_direction(self) -> None:
        """The normal state: rent is settled in full, so a light month
        simply shows its balance the other way."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 1, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        # Bob owes Alice $50, but pays $1981 covering January.
        settlement = make_settlement(
            amount=Decimal("1981.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 4, 26, tzinfo=UTC),
        )
        portion = make_settlement_portion(
            settlement_id=settlement.id,
            year=2026,
            month=1,
            amount=Decimal("1981.00"),
        )
        uow = _setup_uow(
            alice, bob, transactions=[tx], settlements=[settlement], portions=[portion]
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        jan = _month(result, 2026, 1)
        assert jan.charged is not None
        assert jan.charged.amount == Decimal("50.00")
        assert jan.balance is not None
        assert jan.balance.amount == Decimal("1931.00")
        assert jan.balance.from_person_id == alice.id  # swung
        assert jan.status is MonthSettlementStatus.PARTIALLY_SETTLED
        year = _year(result, 2026)
        assert year.balance is not None
        assert year.balance.amount == Decimal("1931.00")
        assert year.balance.from_person_id == alice.id

    async def test_multi_portion_settlement_covers_several_months(self) -> None:
        """A blanket lump stores one portion per covered month — including a
        month that had already swung the other way."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        txs = [
            make_transaction(
                date=date(2026, 1, 15),
                payer_person_id=alice.id,
                amount=Decimal("-100.00"),
                payer_percentage=50,
            ),
            make_transaction(
                date=date(2026, 2, 10),
                payer_person_id=alice.id,
                amount=Decimal("-60.00"),
                payer_percentage=50,
            ),
        ]
        catch_up = make_settlement(
            amount=Decimal("80.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        portions = [
            make_settlement_portion(
                settlement_id=catch_up.id,
                year=2026,
                month=1,
                amount=Decimal("50.00"),
            ),
            make_settlement_portion(
                settlement_id=catch_up.id,
                year=2026,
                month=2,
                amount=Decimal("30.00"),
            ),
        ]
        uow = _setup_uow(
            alice, bob, transactions=txs, settlements=[catch_up], portions=portions
        )
        # The month drill-down only sees February's rows.
        uow.transactions.get_settlement_relevant_by_date_range.return_value = [txs[1]]

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=2), uow
        )

        assert [m.status for m in result.months] == [
            MonthSettlementStatus.SETTLED,
            MonthSettlementStatus.SETTLED,
        ]
        year = _year(result, 2026)
        assert year.balance is None
        entry = result.settlements[0]
        assert [(p.year, p.month, p.amount) for p in entry.application.portions] == [
            (2026, 1, Decimal("50.00")),
            (2026, 2, Decimal("30.00")),
        ]

    async def test_december_portion_counts_toward_the_old_year(self) -> None:
        """A January payment recorded against December belongs to the old
        year — expected every January."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 12, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        payment = make_settlement(
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2027, 1, 4, tzinfo=UTC),
        )
        portion = make_settlement_portion(
            settlement_id=payment.id, year=2026, month=12, amount=Decimal("50.00")
        )
        uow = _setup_uow(
            alice, bob, transactions=[tx], settlements=[payment], portions=[portion]
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2027, month=1), uow
        )

        year_2026 = _year(result, 2026)
        assert year_2026.paid is not None
        assert year_2026.paid.amount == Decimal("50.00")
        assert year_2026.balance is None
        # The requested year is padded in even without activity.
        year_2027 = _year(result, 2027)
        assert year_2027.charged is None
        assert year_2027.balance is None

    async def test_years_padded_with_requested_and_current_year(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = _setup_uow(alice, bob)

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2024, month=6), uow
        )

        years = {y.year for y in result.years}
        assert 2024 in years
        assert datetime.now(UTC).year in years


class TestSettlementRelevantRows:
    async def test_non_household_split_rows_enter_balance_and_audit(self) -> None:
        """Spotted and personal-split rows (household=false) drive the
        settlement balance and appear in the audit splits."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        spotted = make_transaction(
            amount=Decimal("-40.00"),
            payer_person_id=alice.id,
            payer_percentage=0,
            household=False,
            tags=("bob",),
        )
        personal_split = make_transaction(
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
            household=False,
        )
        uow = _setup_uow(alice, bob, transactions=[spotted, personal_split])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        # Bob owes Alice: 40 (spotted) + 30 (personal split) = 70
        jan = _month(result, 2026, 1)
        assert jan.charged is not None
        assert jan.charged.amount == Decimal("70.00")
        assert jan.charged.from_person_id == bob.id
        assert jan.charged.to_person_id == alice.id

        by_payer = {ps.payer_person_id: ps for ps in result.payer_splits}
        assert by_payer[alice.id].total_paid == Decimal("100.00")
        assert by_payer[alice.id].transaction_count == 2


class TestAuditSummaries:
    async def test_payer_splits_and_groups_populated(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        food = make_category_group(name="Food & Dining")
        travel = make_category_group(name="Travel")
        food_cat = make_category(name="Dining Out", group_id=food.id)
        travel_cat = make_category(name="Flights", group_id=travel.id)

        # Alice paid $100 dining 50/50; Bob paid $200 flights 70/30 (Bob 70%).
        txs = [
            make_transaction(
                category="Dining Out",
                payer_person_id=alice.id,
                amount=Decimal("-100.00"),
                payer_percentage=50,
            ),
            make_transaction(
                category="Flights",
                payer_person_id=bob.id,
                amount=Decimal("-200.00"),
                payer_percentage=70,
            ),
        ]
        uow = _setup_uow(
            alice,
            bob,
            transactions=txs,
            categories=[food_cat, travel_cat],
            groups=[food, travel],
        )
        uow.categories.get_all.return_value = [food_cat, travel_cat]
        uow.category_groups.get_all.return_value = [food, travel]

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        # Per-payer aggregate
        assert len(result.payer_splits) == 2
        by_payer = {ps.payer_person_id: ps for ps in result.payer_splits}
        assert by_payer[alice.id].total_paid == Decimal("100.00")
        assert by_payer[alice.id].total_share == Decimal("50.00")
        assert by_payer[alice.id].transaction_count == 1
        assert by_payer[bob.id].total_paid == Decimal("200.00")
        assert by_payer[bob.id].total_share == Decimal("140.00")
        assert by_payer[bob.id].transaction_count == 1

        # Per-(payer x group) — Travel sorts before Food & Dining (larger total)
        assert len(result.payer_group_splits) == 2
        assert result.payer_group_splits[0].group_name == "Travel"
        assert result.payer_group_splits[0].payer_person_id == bob.id
        assert result.payer_group_splits[0].total_paid == Decimal("200.00")
        assert result.payer_group_splits[1].group_name == "Food & Dining"
        assert result.payer_group_splits[1].payer_person_id == alice.id

        # The audit-row sum (paid - share) reconciles to the month's charge.
        # Alice fronted $100, owes $50 of it — Bob owes Alice $50.
        # Bob fronted $200, owes $140 of it — Alice owes Bob $60.
        # Net: Alice owes Bob $10 → charged: from=Alice, to=Bob, $10.
        jan = _month(result, 2026, 1)
        assert jan.charged is not None
        assert jan.charged.from_person_id == alice.id
        assert jan.charged.to_person_id == bob.id
        assert jan.charged.amount == Decimal("10.00")


class TestFinalizationWarnings:
    def _setup_uow(
        self,
        alice,
        bob,
        *,
        uploads_for: list | None = None,
        has_balance: bool = False,
        unmapped_category: bool = False,
        is_finalized: bool = False,
    ):
        group = make_category_group()
        category = make_category(group_id=group.id)
        categories = [category]
        if unmapped_category:
            categories.append(make_category(name="Unmapped Thing", group_id=None))

        txs = []
        if has_balance:
            txs.append(
                make_transaction(
                    payer_person_id=alice.id,
                    amount=Decimal("-100.00"),
                    payer_percentage=50,
                    category=category.name,
                )
            )
        if unmapped_category:
            txs.append(
                make_transaction(
                    payer_person_id=alice.id,
                    amount=Decimal("-10.00"),
                    payer_percentage=50,
                    category="Unmapped Thing",
                )
            )

        uploads = [make_upload(person_id=pid) for pid in (uploads_for or [])]

        uow = _setup_uow(
            alice,
            bob,
            transactions=txs,
            categories=categories,
            groups=[group],
            uploads=uploads,
        )
        uow.categories.get_all.return_value = categories

        if is_finalized:
            uow.reconciliation_periods.get_by_period.return_value = (
                make_reconciliation_period(year=2026, month=1, is_finalized=True)
            )

        return uow

    async def test_warns_missing_upload(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(alice, bob, uploads_for=[alice.id])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert any("No upload from Bob" in w for w in result.finalization_warnings)

    async def test_warns_outstanding_balance_for_the_months_year(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice, bob, uploads_for=[alice.id, bob.id], has_balance=True
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert any(
            "Outstanding balance of $50.00 in 2026" in w
            for w in result.finalization_warnings
        )

    async def test_ignores_a_balance_carried_by_another_year(self) -> None:
        """Locking a 2027 month answers for 2027 — a 2026 debt is not its
        problem."""
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice, bob, uploads_for=[alice.id, bob.id], has_balance=True
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2027, month=1), uow
        )
        assert not any("Outstanding balance" in w for w in result.finalization_warnings)

    async def test_warns_unmapped_categories(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice, bob, uploads_for=[alice.id, bob.id], unmapped_category=True
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert any("unmapped categories" in w for w in result.finalization_warnings)

    async def test_no_warnings_when_all_clear(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(alice, bob, uploads_for=[alice.id, bob.id])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert result.finalization_warnings == []

    async def test_no_warnings_when_finalized(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice,
            bob,
            uploads_for=[],
            has_balance=True,
            unmapped_category=True,
            is_finalized=True,
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert result.finalization_warnings == []


async def test_split_transfer_row_does_not_enter_the_ledger() -> None:
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    food = make_category_group(name="Food & Dining")
    transfer = make_category_group(name="Transfer", kind="transfer")
    uow = _setup_uow(
        alice,
        bob,
        groups=[food, transfer],
        categories=[
            make_category(name="Dining Out", group_id=food.id),
            make_category(name="Credit Card Payment", group_id=transfer.id),
        ],
        transactions=[
            make_transaction(
                date=date(2026, 1, 5),
                category="Dining Out",
                amount=Decimal("-40.00"),
                payer_person_id=alice.id,
                payer_percentage=50,
            ),
            make_transaction(
                date=date(2026, 1, 6),
                category="Credit Card Payment",
                amount=Decimal("-900.00"),
                payer_person_id=alice.id,
                payer_percentage=50,
            ),
        ],
    )

    result = await GetSettleUpDataUseCase().execute(
        GetSettleUpDataCommand(year=2026, month=1), uow
    )

    year = next(y for y in result.years if y.year == 2026)
    assert year.balance is not None
    assert year.balance.amount == Decimal("20.00")
    assert year.balance.from_person_id == bob.id
