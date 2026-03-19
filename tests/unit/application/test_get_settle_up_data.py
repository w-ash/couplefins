from decimal import Decimal

from src.application.use_cases.get_settle_up_data import (
    GetSettleUpDataCommand,
    GetSettleUpDataUseCase,
)
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_person,
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
        uow.settlement_transaction_links.get_by_settlement_id.return_value = []
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = [
            make_upload(person_id=alice.id)
        ]

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.year == 2026
        assert result.month == 1
        assert result.owed is not None
        assert result.owed.amount == Decimal("50.00")
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
        uow.settlement_transaction_links.get_by_settlement_id.return_value = []
        uow.uploads.get_by_person_ids_with_transactions_in_date_range.return_value = []

        command = GetSettleUpDataCommand(year=2026, month=1)
        result = await GetSettleUpDataUseCase().execute(command, uow)

        assert result.remaining_balance == Decimal(0)
