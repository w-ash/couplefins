from uuid import UUID

import pytest

from src.application.use_cases.delete_budget import (
    DeleteBudgetCommand,
    DeleteBudgetUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_deletes_budget_and_commits() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget()
    uow.category_group_budgets.get_by_id.return_value = existing

    command = DeleteBudgetCommand(budget_id=existing.id)
    await DeleteBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.delete.assert_called_once_with(existing.id)
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_budget() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_id.return_value = None

    command = DeleteBudgetCommand(
        budget_id=UUID("00000000-0000-0000-0000-000000000001")
    )

    with pytest.raises(NotFoundError):
        await DeleteBudgetUseCase().execute(command, uow)
