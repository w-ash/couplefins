import pytest

from src.application.use_cases.delete_category_group import (
    DeleteCategoryGroupCommand,
    DeleteCategoryGroupUseCase,
)
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_category_group
from tests.fixtures.mocks import make_mock_uow


async def test_unmaps_categories_and_deletes_group() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    command = DeleteCategoryGroupCommand(group_id=group.id)

    await DeleteCategoryGroupUseCase().execute(command, uow)

    uow.categories.unmap_by_group_id.assert_called_once_with(group.id)
    uow.category_group_budgets.delete_by_group_id.assert_called_once_with(group.id)
    uow.category_groups.delete.assert_called_once_with(group.id)
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = DeleteCategoryGroupCommand(group_id=make_category_group().id)

    with pytest.raises(NotFoundError):
        await DeleteCategoryGroupUseCase().execute(command, uow)


async def test_moves_categories_to_target_group() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    target = make_category_group(name="Home Expenses")
    uow.category_groups.get_by_id.side_effect = lambda gid: (
        group if gid == group.id else target if gid == target.id else None
    )
    command = DeleteCategoryGroupCommand(
        group_id=group.id, move_categories_to=target.id
    )

    await DeleteCategoryGroupUseCase().execute(command, uow)

    uow.categories.remap_by_group_id.assert_called_once_with(group.id, target.id)
    uow.categories.unmap_by_group_id.assert_not_called()
    uow.category_group_budgets.delete_by_group_id.assert_called_once_with(group.id)
    uow.category_groups.delete.assert_called_once_with(group.id)
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_target_group() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.side_effect = lambda gid: (
        group if gid == group.id else None
    )
    missing_target = make_category_group(name="Nonexistent")
    command = DeleteCategoryGroupCommand(
        group_id=group.id, move_categories_to=missing_target.id
    )

    with pytest.raises(NotFoundError, match="Target"):
        await DeleteCategoryGroupUseCase().execute(command, uow)


async def test_raises_validation_error_for_self_move() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    command = DeleteCategoryGroupCommand(group_id=group.id, move_categories_to=group.id)

    with pytest.raises(ValidationError, match="same group"):
        await DeleteCategoryGroupUseCase().execute(command, uow)
