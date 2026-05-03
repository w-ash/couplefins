from decimal import Decimal

from src.application.use_cases.get_settle_up_data import (
    GetSettleUpDataCommand,
    GetSettleUpDataUseCase,
)
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
        group = make_category_group()
        category = make_category(group_id=group.id)

        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.transactions.get_household_by_date_range.return_value = [tx]
        uow.categories.get_all.return_value = [category]
        uow.category_groups.get_all.return_value = [group]
        uow.settlements.get_by_period.return_value = [settlement]
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = [
            make_upload(person_id=alice.id)
        ]

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
        group = make_category_group()
        category = make_category(group_id=group.id)

        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.transactions.get_household_by_date_range.return_value = [tx]
        uow.categories.get_all.return_value = [category]
        uow.category_groups.get_all.return_value = [group]
        uow.settlements.get_by_period.return_value = [settlement]
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = []

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.net_position is None
        assert result.remaining_balance == Decimal(0)

    async def test_overpayment_reverses_net_position(self) -> None:
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
        group = make_category_group()
        category = make_category(group_id=group.id)

        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.transactions.get_household_by_date_range.return_value = [tx]
        uow.categories.get_all.return_value = [category]
        uow.category_groups.get_all.return_value = [group]
        uow.settlements.get_by_period.return_value = [settlement]
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = []

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        # Gross still shows Bob owes Alice $50
        assert result.owed is not None
        assert result.owed.amount == Decimal("50.00")
        assert result.owed.from_person_id == bob.id

        # Net position reverses: Alice now owes Bob $1931
        assert result.net_position is not None
        assert result.net_position.amount == Decimal("1931.00")
        assert result.net_position.from_person_id == alice.id
        assert result.net_position.to_person_id == bob.id
        assert result.remaining_balance == Decimal("1931.00")


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

        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.transactions.get_household_by_date_range.return_value = txs
        uow.categories.get_all.return_value = [food_cat, travel_cat]
        uow.category_groups.get_all.return_value = [food, travel]
        uow.settlements.get_by_period.return_value = []
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = []

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

        uow = make_mock_uow()
        uow.persons.get_all.return_value = [alice, bob]
        uow.transactions.get_household_by_date_range.return_value = txs
        uow.categories.get_all.return_value = categories
        uow.category_groups.get_all.return_value = [group]
        uow.settlements.get_by_period.return_value = []
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = (
            uploads
        )

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

    async def test_warns_unsettled_balance(self) -> None:
        alice = make_person(name="Alice")
        bob = make_person(name="Bob")
        uow = self._setup_uow(
            alice, bob, uploads_for=[alice.id, bob.id], has_balance=True
        )

        result = await GetSettleUpDataUseCase().execute(
            GetSettleUpDataCommand(year=2026, month=1), uow
        )
        assert any("Unsettled balance" in w for w in result.finalization_warnings)

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
