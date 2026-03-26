import pytest

from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewUseCase,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import (
    make_category_group,
    make_category_group_budget,
    make_person,
)
from tests.fixtures.mocks import make_mock_uow


async def test_returns_overview_and_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    budget = make_category_group_budget(group_id=group.id)

    uow.category_group_budgets.get_by_person.return_value = [budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.year == 2026
    assert result.overview.month == 1
    assert result.budgets == [budget]
    uow.category_group_budgets.get_by_person.assert_called_once_with(None)
    uow.transactions.get_household_by_year.assert_called_once_with(2026)


async def test_returns_empty_overview_when_no_data() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_person.return_value = []
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = []
    uow.transactions.get_household_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=3)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.group_statuses == []
    assert result.budgets == []


async def test_personal_scope_calls_get_by_person() -> None:
    uow = make_mock_uow()
    alice = make_person(name="Alice")
    group = make_category_group()
    budget = make_category_group_budget(group_id=group.id, person_id=alice.id)

    uow.category_group_budgets.get_by_person.return_value = [budget]
    uow.categories.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.persons.get_all.return_value = [alice]
    uow.transactions.get_by_year.return_value = []

    command = GetBudgetOverviewCommand(
        year=2026, month=1, scope="personal", person_id=alice.id
    )
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    uow.category_group_budgets.get_by_person.assert_called_once_with(alice.id)
    uow.transactions.get_by_year.assert_called_once_with(2026)
    assert result.budgets == [budget]


def test_personal_scope_requires_person_id() -> None:
    with pytest.raises(ValidationError, match="person_id is required"):
        GetBudgetOverviewCommand(year=2026, month=1, scope="personal")
