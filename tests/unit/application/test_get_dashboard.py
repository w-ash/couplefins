from datetime import date
from decimal import Decimal

from src.application.use_cases.get_dashboard import (
    GetDashboardCommand,
    GetDashboardUseCase,
)
from tests.fixtures.factories import (
    make_category_group,
    make_category_mapping,
    make_person,
    make_transaction,
    make_upload,
)
from tests.fixtures.mocks import make_mock_uow


def _make_command(year: int = 2026, month: int = 3) -> GetDashboardCommand:
    return GetDashboardCommand(year=year, month=month)


def _setup_uow_base(uow, alice, bob, *, groups=None, mappings=None):
    uow.persons.get_all.return_value = [alice, bob]
    uow.category_groups.get_all.return_value = groups or []
    uow.category_mappings.get_all.return_value = mappings or []


async def test_happy_path_current_month() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    group = make_category_group(name="Food & Dining")
    mapping = make_category_mapping(category="Dining Out", group_id=group.id)
    _setup_uow_base(uow, alice, bob, groups=[group], mappings=[mapping])

    txs = [
        make_transaction(
            date=date(2026, 3, 10),
            category="Dining Out",
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_year.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = [
        make_upload(person_id=alice.id),
        make_upload(person_id=bob.id),
    ]

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.current_month.year == 2026
    assert result.current_month.month == 3
    assert result.current_month.total_shared_spending == Decimal("100.00")
    assert result.current_month.transaction_count == 1
    assert all(s.has_uploaded for s in result.upload_statuses)


async def test_empty_month_zeroed_summary() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    uow.transactions.get_shared_by_year.return_value = []
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert result.current_month.transaction_count == 0
    assert result.current_month.total_shared_spending == Decimal(0)
    assert result.ytd_total_shared_spending == Decimal(0)
    assert result.month_history == []


async def test_multi_month_history() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-80.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_year.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    assert len(result.month_history) == 3
    # Sorted newest first
    assert result.month_history[0].month == 3
    assert result.month_history[1].month == 2
    assert result.month_history[2].month == 1
    # Each month has correct spending
    assert result.month_history[0].total_shared_spending == Decimal("100.00")
    assert result.month_history[1].total_shared_spending == Decimal("80.00")
    assert result.month_history[2].total_shared_spending == Decimal("60.00")


async def test_ytd_aggregates_across_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 2, 10),
            amount=Decimal("-60.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        make_transaction(
            date=date(2026, 3, 5),
            amount=Decimal("-40.00"),
            payer_person_id=bob.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_year.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # YTD = $100 + $60 + $40 = $200
    assert result.ytd_total_shared_spending == Decimal("200.00")
    # YTD settlement: Alice paid $160, Bob paid $40. Each share = $100.
    # Alice overpaid by $60 → Bob owes Alice $60.
    assert result.ytd_settlement is not None
    assert result.ytd_settlement.amount == Decimal("60.00")
    assert result.ytd_settlement.from_person_id == bob.id
    assert result.ytd_settlement.to_person_id == alice.id


async def test_ytd_excludes_future_months() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
        # April is after March (the requested month)
        make_transaction(
            date=date(2026, 4, 10),
            amount=Decimal("-200.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_year.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    # YTD should only include January, not April
    assert result.ytd_total_shared_spending == Decimal("100.00")
    # Current month (March) should be empty
    assert result.current_month.transaction_count == 0


async def test_settlement_history_entries() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    _setup_uow_base(uow, alice, bob)

    txs = [
        make_transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-100.00"),
            payer_person_id=alice.id,
            payer_percentage=50,
        ),
    ]
    uow.transactions.get_shared_by_year.return_value = txs
    uow.uploads.get_by_person_ids_with_transactions_in_period.return_value = []

    result = await GetDashboardUseCase().execute(_make_command(), uow)

    jan_entry = result.month_history[-1]
    assert jan_entry.month == 1
    assert jan_entry.settlement_amount == Decimal("50.00")
    assert jan_entry.settlement_from_person_id == bob.id
    assert jan_entry.settlement_to_person_id == alice.id
