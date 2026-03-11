from decimal import Decimal

from src.application.use_cases.get_reconciliation import (
    GetReconciliationCommand,
    GetReconciliationUseCase,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_mapping,
    make_person,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def _make_command(year: int = 2026, month: int = 1) -> GetReconciliationCommand:
    return GetReconciliationCommand(year=year, month=month)


async def test_happy_path_both_uploaded() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]

    group = make_category_group(name="Food & Dining")
    mapping = make_category_mapping(category="Dining Out", group_id=group.id)
    uow.category_groups.get_all.return_value = [group]
    uow.category_mappings.get_all.return_value = [mapping]

    txs = [
        make_transaction(
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Dining Out",
            amount=Decimal("-60.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_period.return_value = txs

    uploads = [
        make_upload(person_id=alice.id),
        make_upload(person_id=bob.id),
    ]
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = uploads

    result = await GetReconciliationUseCase().execute(_make_command(), uow)

    assert result.summary.year == 2026
    assert result.summary.month == 1
    assert result.summary.transaction_count == 2
    assert result.summary.total_shared_spending == Decimal("160.00")
    assert result.summary.settlement is not None
    assert all(s.has_uploaded for s in result.upload_statuses)
    assert len(result.transactions) == 2
    assert result.unmapped_categories == []


async def test_partial_upload_one_person() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]
    uow.category_groups.get_all.return_value = []
    uow.category_mappings.get_all.return_value = []

    txs = [
        make_transaction(
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_period.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = [
        make_upload(person_id=alice.id)
    ]

    result = await GetReconciliationUseCase().execute(_make_command(), uow)

    alice_status = next(s for s in result.upload_statuses if s.person_id == alice.id)
    bob_status = next(s for s in result.upload_statuses if s.person_id == bob.id)
    assert alice_status.has_uploaded is True
    assert alice_status.upload_count == 1
    assert bob_status.has_uploaded is False
    assert bob_status.upload_count == 0


async def test_empty_month_no_transactions() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]
    uow.category_groups.get_all.return_value = []
    uow.category_mappings.get_all.return_value = []
    uow.transactions.get_shared_by_period.return_value = []
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetReconciliationUseCase().execute(_make_command(), uow)

    assert result.summary.transaction_count == 0
    assert result.summary.total_shared_spending == Decimal(0)
    assert result.summary.settlement is not None
    assert result.summary.settlement.amount == Decimal(0)
    assert result.transactions == []
    assert all(not s.has_uploaded for s in result.upload_statuses)


async def test_unmapped_categories_detected() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    uow.persons.get_all.return_value = [alice, bob]
    uow.category_groups.get_all.return_value = []
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Dining Out"),
    ]

    txs = [
        make_transaction(
            category="Dining Out",
            amount=Decimal("-50.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            category="Unknown Service",
            amount=Decimal("-20.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_period.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetReconciliationUseCase().execute(_make_command(), uow)

    assert result.unmapped_categories == ["Unknown Service"]
