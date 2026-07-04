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
    categories: list | None = None,
    groups: list | None = None,
    uploads: list | None = None,
):
    """Wire both the ledger fetches (all-time) and the month audit fetches
    from one dataset — mirroring a database where they are the same rows."""
    group = groups[0] if groups else make_category_group()
    category = (categories or [make_category(group_id=group.id)])[0]
    txs = transactions or []
    stls = settlements or []

    uow = make_mock_uow()
    uow.persons.get_all.return_value = [alice, bob]
    uow.categories.get_all.return_value = categories or [category]
    uow.category_groups.get_all.return_value = groups or [group]
    # Ledger (all-time) fetches
    uow.transactions.get_all_settlement_relevant.return_value = txs
    uow.settlements.get_all.return_value = stls
    # Month audit fetches — callers pass month-scoped rows via these kwargs
    uow.transactions.get_settlement_relevant_by_date_range.return_value = txs
    uow.settlements.get_by_period.return_value = stls
    uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = (
        uploads or []
    )
    return uow


class TestGetSettleUpData:
    async def test_returns_owed_and_remaining(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        settlement = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("30.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        uow = _setup_uow(
            alice,
            bob,
            transactions=[tx],
            settlements=[settlement],
            uploads=[make_upload(person_id=alice.id)],
        )

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.year == 2026
        assert result.month == 1
        assert result.owed is not None
        assert result.owed.amount == Decimal("50.00")
        assert result.net_position is not None
        assert result.net_position.amount == Decimal("20.00")
        assert result.net_position.from_person_id == bob.id
        assert result.net_position.to_person_id == alice.id
        assert result.remaining_balance == Decimal("20.00")
        assert len(result.recorded_settlements) == 1
        assert result.is_finalized is False
        # Ledger fields
        assert result.outstanding is not None
        assert result.outstanding.amount == Decimal("20.00")
        assert result.outstanding_span == ((2026, 1), (2026, 1))
        assert len(result.ledger_months) == 1
        jan = result.ledger_months[0]
        assert (jan.year, jan.month) == (2026, 1)
        assert jan.applied == Decimal("30.00")
        assert jan.remaining == Decimal("20.00")
        assert jan.status is MonthSettlementStatus.PARTIALLY_SETTLED
        assert jan.covering_settlement_ids == (settlement.id,)
        assert len(result.all_settlements) == 1
        coverage = result.all_settlements[0].coverage
        assert coverage.covered == ((2026, 1, Decimal("30.00")),)
        assert coverage.unapplied == Decimal(0)

    async def test_returns_zero_remaining_when_settled(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        settlement = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=[settlement])

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.net_position is None
        assert result.remaining_balance == Decimal(0)
        assert result.outstanding is None
        assert result.outstanding_span is None
        assert result.ledger_months[0].status is MonthSettlementStatus.SETTLED

    async def test_overpayment_settles_month_and_reverses_outstanding(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        # Bob owes Alice $50, but pays $1981
        settlement = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("1981.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=[settlement])

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        # Gross still shows Bob owes Alice $50
        assert result.owed is not None
        assert result.owed.amount == Decimal("50.00")
        assert result.owed.from_person_id == bob.id

        # The month itself is fully covered — nothing remains against it.
        assert result.net_position is None
        assert result.remaining_balance == Decimal(0)
        assert result.ledger_months[0].status is MonthSettlementStatus.SETTLED

        # The excess rides on the ledger as a reversed outstanding balance.
        assert result.outstanding is not None
        assert result.outstanding.amount == Decimal("1931.00")
        assert result.outstanding.from_person_id == alice.id
        assert result.outstanding.to_person_id == bob.id
        assert result.all_settlements[0].coverage.unapplied == Decimal("1931.00")

    async def test_multiple_settlements_in_one_month_apply_cumulatively(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-200.00"),
            payer_percentage=50,
        )
        earlier = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
        later = datetime(2026, 2, 5, 14, 0, tzinfo=UTC)
        payments = [
            make_settlement(
                year=2026,
                month=1,
                amount=Decimal("60.00"),
                from_person_id=bob.id,
                to_person_id=alice.id,
                settled_at=earlier,
            ),
            make_settlement(
                year=2026,
                month=1,
                amount=Decimal("40.00"),
                from_person_id=bob.id,
                to_person_id=alice.id,
                settled_at=later,
            ),
        ]
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=payments)

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        assert result.net_position is None
        assert result.outstanding is None
        jan = result.ledger_months[0]
        assert jan.status is MonthSettlementStatus.SETTLED
        assert jan.covering_settlement_ids == (payments[0].id, payments[1].id)

    async def test_settlement_recorded_after_month_end_still_covers_it(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            date=date(2026, 1, 15),
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        # Paid during the April together session.
        payment = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("50.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 4, 12, tzinfo=UTC),
        )
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=[payment])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        assert result.net_position is None
        assert result.outstanding is None
        assert result.ledger_months[0].status is MonthSettlementStatus.SETTLED

    async def test_catch_up_payment_covers_multiple_months(self) -> None:
        """One payment settles two open months FIFO; the drill-down month's
        position reflects only its own remainder."""
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
            year=None,
            month=None,
            amount=Decimal("80.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
            settled_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        uow = _setup_uow(alice, bob, transactions=txs, settlements=[catch_up])
        # The month drill-down only sees February's rows.
        uow.transactions.get_settlement_relevant_by_date_range.return_value = [txs[1]]
        uow.settlements.get_by_period.return_value = []

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=2), uow
        )

        # $50 (Jan) + $30 (Feb) fully covered by the $80 catch-up.
        assert result.outstanding is None
        assert result.net_position is None
        assert [m.status for m in result.ledger_months] == [
            MonthSettlementStatus.SETTLED,
            MonthSettlementStatus.SETTLED,
        ]
        coverage = result.all_settlements[0].coverage
        assert coverage.covered == (
            (2026, 1, Decimal("50.00")),
            (2026, 2, Decimal("30.00")),
        )
        # The un-annotated payment still shows in the all-time history.
        assert result.all_settlements[0].record.settlement.year is None

    async def test_partial_payment_leaves_month_partially_settled(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        tx = make_transaction(
            payer_person_id=alice.id,
            amount=Decimal("-100.00"),
            payer_percentage=50,
        )
        partial = make_settlement(
            year=2026,
            month=1,
            amount=Decimal("20.00"),
            from_person_id=bob.id,
            to_person_id=alice.id,
        )
        uow = _setup_uow(alice, bob, transactions=[tx], settlements=[partial])

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )

        assert result.net_position is not None
        assert result.net_position.amount == Decimal("30.00")
        assert result.remaining_balance == Decimal("30.00")
        assert result.ledger_months[0].status is (
            MonthSettlementStatus.PARTIALLY_SETTLED
        )


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
        assert result.owed is not None
        assert result.owed.amount == Decimal("70.00")
        assert result.owed.from_person_id == bob.id
        assert result.owed.to_person_id == alice.id
        assert result.outstanding is not None
        assert result.outstanding.amount == Decimal("70.00")

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

        # The audit-row sum (paid - share) reconciles to the gross owed amount.
        # Alice fronted $100, owes $50 of it — Bob owes Alice $50.
        # Bob fronted $200, owes $140 of it — Alice owes Bob $60.
        # Net: Alice owes Bob $10 → owed: from=Alice, to=Bob, amount=$10.
        assert result.owed is not None
        assert result.owed.from_person_id == alice.id
        assert result.owed.to_person_id == bob.id
        assert result.owed.amount == Decimal("10.00")


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

    async def test_warns_outstanding_balance_across_all_months(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice, bob, uploads_for=[alice.id, bob.id], has_balance=True
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert any(
            "Outstanding balance of $50.00 across all months" in w
            for w in result.finalization_warnings
        )

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
