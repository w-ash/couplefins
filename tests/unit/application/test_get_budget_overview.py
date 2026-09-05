from decimal import Decimal

import pytest

from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import (
    make_category,
    make_category_group,
    make_category_group_budget,
    make_person,
    make_transaction,
    make_transfer_group,
)
from tests.fixtures.mocks import make_mock_uow


async def test_returns_overview_and_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    budget = make_category_group_budget(group_id=group.id)

    uow.category_group_budgets.get_by_year.return_value = [budget]
    uow.category_group_budgets.get_all.return_value = [budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.year == 2026
    assert result.overview.month == 1
    assert result.budgets == [budget]
    uow.category_group_budgets.get_by_year.assert_called_once_with(2026, None)
    uow.transactions.get_household_by_year.assert_called_once_with(2026)


async def test_returns_empty_overview_when_no_data() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_year.return_value = []
    uow.category_group_budgets.get_all.return_value = []
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = []
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=3)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.group_statuses == []
    assert result.budgets == []


async def test_personal_scope_calls_get_by_year() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    group = make_category_group()
    budget = make_category_group_budget(group_id=group.id, person_id=alice.id)

    uow.category_group_budgets.get_by_year.return_value = [budget]
    uow.category_group_budgets.get_all.return_value = [budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.persons.get_all.return_value = [alice]
    uow.transactions.get_by_year.return_value = []

    command = GetBudgetOverviewCommand(
        year=2026, month=1, scope="personal", person_id=alice.id
    )
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    uow.category_group_budgets.get_by_year.assert_called_once_with(2026, alice.id)
    uow.transactions.get_by_year.assert_called_once_with(2026)
    assert result.budgets == [budget]


async def test_copyable_source_returns_most_recent_prior_month() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    jan_budget = make_category_group_budget(group_id=group.id, year=2026, month=1)
    feb_budget = make_category_group_budget(group_id=group.id, year=2026, month=2)

    uow.category_group_budgets.get_by_year.return_value = []
    uow.category_group_budgets.get_all.return_value = [jan_budget, feb_budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=3)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.copyable_source == (2026, 2)


async def test_copyable_source_crosses_year_boundary() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    dec_budget = make_category_group_budget(group_id=group.id, year=2025, month=12)

    uow.category_group_budgets.get_by_year.return_value = []
    uow.category_group_budgets.get_all.return_value = [dec_budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.copyable_source == (2025, 12)


async def test_copyable_source_none_when_no_prior_budgets() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_year.return_value = []
    uow.category_group_budgets.get_all.return_value = []
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = []
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.copyable_source is None
    assert result.source_budgets == []


async def test_next_month_has_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    jan_budget = make_category_group_budget(group_id=group.id, year=2026, month=1)
    feb_budget = make_category_group_budget(group_id=group.id, year=2026, month=2)

    uow.category_group_budgets.get_by_year.return_value = [jan_budget]
    uow.category_group_budgets.get_all.return_value = [jan_budget, feb_budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.next_month_has_budgets is True


async def test_next_month_has_no_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    jan_budget = make_category_group_budget(group_id=group.id, year=2026, month=1)

    uow.category_group_budgets.get_by_year.return_value = [jan_budget]
    uow.category_group_budgets.get_all.return_value = [jan_budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.next_month_has_budgets is False


async def test_source_budgets_populated_from_copyable_source() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    jan_budget = make_category_group_budget(group_id=group.id, year=2026, month=1)

    uow.category_group_budgets.get_by_year.return_value = []
    uow.category_group_budgets.get_all.return_value = [jan_budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=2)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.copyable_source == (2026, 1)
    assert result.source_budgets == [jan_budget]


def test_personal_scope_requires_person_id() -> None:
    with pytest.raises(ValidationError, match="person_id is required"):
        GetBudgetOverviewCommand(year=2026, month=1, scope="personal")


async def test_transfer_rows_never_reach_the_budget() -> None:
    """A credit card payment is money movement: dropped in both scopes, and
    its group gets no status row."""
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    uow.persons.get_all.return_value = [alice]
    food = make_category_group(name="Food & Dining")
    transfer, card_payment = make_transfer_group()
    uow.category_groups.get_all.return_value = [food, transfer]
    uow.categories.get_all.return_value = [
        make_category(name="Dining Out", group_id=food.id),
        card_payment,
    ]
    uow.category_group_budgets.get_by_year.return_value = []
    txs = [
        make_transaction(
            category="Dining Out", amount=Decimal("-80.00"), payer_person_id=alice.id
        ),
        make_transaction(
            category="Credit Card Payment",
            amount=Decimal("-2000.00"),
            payer_person_id=alice.id,
            payer_percentage=100,
            household=False,
            tags=(),
        ),
        make_transaction(
            category="Credit Card Payment",
            amount=Decimal("-500.00"),
            payer_person_id=alice.id,
        ),
    ]
    uow.transactions.get_household_by_year.return_value = txs
    uow.transactions.get_by_year.return_value = txs

    household = await GetBudgetOverviewUseCase().execute(
        GetBudgetOverviewCommand(year=2026, month=1), uow
    )
    personal = await GetBudgetOverviewUseCase().execute(
        GetBudgetOverviewCommand(
            year=2026, month=1, scope="personal", person_id=alice.id
        ),
        uow,
    )

    assert [s.group_name for s in household.overview.group_statuses] == [
        "Food & Dining"
    ]
    assert household.overview.total_ytd_spent == Decimal("80.00")
    assert [s.group_name for s in personal.overview.group_statuses] == ["Food & Dining"]
    assert personal.overview.total_ytd_spent == Decimal("40.00")
