import pytest

from src.application.use_cases.update_category_group import (
    UpdateCategoryGroupCommand,
    UpdateCategoryGroupUseCase,
)
from src.domain.exceptions import NotFoundError
from tests.fixtures.factories import make_category_group
from tests.fixtures.mocks import make_mock_uow


async def test_updates_group_name() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Old Name")
    uow.category_groups.get_by_id.return_value = group
    command = UpdateCategoryGroupCommand(id=group.id, name="New Name")

    await UpdateCategoryGroupUseCase().execute(command, uow)

    saved = uow.category_groups.save.call_args[0][0]
    assert saved.name == "New Name"
    assert saved.id == group.id
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = UpdateCategoryGroupCommand(id=make_category_group().id, name="New Name")

    with pytest.raises(NotFoundError):
        await UpdateCategoryGroupUseCase().execute(command, uow)
