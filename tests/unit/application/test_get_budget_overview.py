from src.application.use_cases.get_budget_overview import (
    GetBudgetOverviewCommand,
    GetBudgetOverviewUseCase,
)
from tests.fixtures.factories import make_category_group, make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_returns_overview_and_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    budget = make_category_group_budget(group_id=group.id)

    uow.category_group_budgets.get_all.return_value = [budget]
    uow.category_mappings.get_all.return_value = []
    uow.category_groups.get_all.return_value = [group]
    uow.transactions.get_shared_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=1)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.year == 2026
    assert result.overview.month == 1
    assert result.budgets == [budget]
    uow.transactions.get_shared_by_year.assert_called_once_with(2026)


async def test_returns_empty_overview_when_no_data() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_all.return_value = []
    uow.category_mappings.get_all.return_value = []
    uow.category_groups.get_all.return_value = []
    uow.transactions.get_shared_by_year.return_value = []

    command = GetBudgetOverviewCommand(year=2026, month=3)
    result = await GetBudgetOverviewUseCase().execute(command, uow)

    assert result.overview.group_statuses == []
    assert result.budgets == []
