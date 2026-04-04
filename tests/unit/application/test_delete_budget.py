from uuid import UUID

import pytest

from src.application.use_cases.delete_budget import (
    DeleteBudgetCommand,
    DeleteBudgetUseCase,
)
from src.domain.exceptions import ForbiddenError, NotFoundError
from tests.fixtures.factories import make_category_group_budget
from tests.fixtures.mocks import make_mock_uow

ALICE = UUID("bbbbbbbb-0000-0000-0000-000000000001")
BOB = UUID("bbbbbbbb-0000-0000-0000-000000000002")


async def test_deletes_budget_and_commits() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget()
    uow.category_group_budgets.get_by_id.return_value = existing

    command = DeleteBudgetCommand(budget_id=existing.id, person_id=ALICE)
    await DeleteBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.delete.assert_called_once_with(existing.id)
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_budget() -> None:
    uow = make_mock_uow()
    uow.category_group_budgets.get_by_id.return_value = None

    command = DeleteBudgetCommand(
        budget_id=UUID("00000000-0000-0000-0000-000000000001"),
        person_id=ALICE,
    )

    with pytest.raises(NotFoundError):
        await DeleteBudgetUseCase().execute(command, uow)


async def test_rejects_other_persons_personal_budget() -> None:
    uow = make_mock_uow()
    existing = make_category_group_budget(person_id=ALICE)
    uow.category_group_budgets.get_by_id.return_value = existing

    command = DeleteBudgetCommand(budget_id=existing.id, person_id=BOB)

    with pytest.raises(ForbiddenError):
        await DeleteBudgetUseCase().execute(command, uow)


async def test_allows_deleting_household_budget() -> None:
    """Household budgets (person_id=None) are deletable by anyone."""
    uow = make_mock_uow()
    existing = make_category_group_budget(person_id=None)
    uow.category_group_budgets.get_by_id.return_value = existing

    command = DeleteBudgetCommand(budget_id=existing.id, person_id=ALICE)
    await DeleteBudgetUseCase().execute(command, uow)

    uow.category_group_budgets.delete.assert_called_once_with(existing.id)
