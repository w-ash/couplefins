import pytest

from src.application.use_cases.delete_category_group import (
    DeleteCategoryGroupCommand,
    DeleteCategoryGroupUseCase,
)
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_category_group, make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_deletes_group_and_mappings() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_group_id.return_value = []
    command = DeleteCategoryGroupCommand(group_id=group.id)

    await DeleteCategoryGroupUseCase().execute(command, uow)

    uow.category_mappings.delete_by_group_id.assert_called_once_with(group.id)
    uow.category_groups.delete.assert_called_once_with(group.id)
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = DeleteCategoryGroupCommand(group_id=make_category_group().id)

    with pytest.raises(NotFoundError):
        await DeleteCategoryGroupUseCase().execute(command, uow)


async def test_raises_validation_error_when_budgets_exist() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_group_id.return_value = [
        make_category_group_budget(group_id=group.id)
    ]
    command = DeleteCategoryGroupCommand(group_id=group.id)

    with pytest.raises(ValidationError, match="budget"):
        await DeleteCategoryGroupUseCase().execute(command, uow)
