import pytest

from src.application.use_cases.update_category_group import (
    UpdateCategoryGroupCommand,
    UpdateCategoryGroupUseCase,
)
from src.domain.exceptions import NotFoundError, ValidationError
from tests.fixtures.factories import make_category_group, make_category_group_budget
from tests.fixtures.mocks import make_mock_uow


async def test_updates_group_name() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Old Name")
    uow.category_groups.get_by_id.return_value = group
    command = UpdateCategoryGroupCommand(id=group.id, name="New Name", kind="expense")

    await UpdateCategoryGroupUseCase().execute(command, uow)

    saved = uow.category_groups.save.call_args[0][0]
    assert saved.name == "New Name"
    assert saved.id == group.id
    uow.commit.assert_called_once()


async def test_raises_not_found_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = UpdateCategoryGroupCommand(
        id=make_category_group().id, name="New Name", kind="expense"
    )

    with pytest.raises(NotFoundError):
        await UpdateCategoryGroupUseCase().execute(command, uow)


async def test_marks_group_as_transfer() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Transfer")
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_group_id.return_value = []
    command = UpdateCategoryGroupCommand(id=group.id, name="Transfer", kind="transfer")

    await UpdateCategoryGroupUseCase().execute(command, uow)

    assert uow.category_groups.save.call_args[0][0].kind == "transfer"


async def test_rename_keeps_transfer_kind_when_passed() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Transfer", kind="transfer")
    uow.category_groups.get_by_id.return_value = group
    command = UpdateCategoryGroupCommand(id=group.id, name="Transfers", kind="transfer")

    await UpdateCategoryGroupUseCase().execute(command, uow)

    saved = uow.category_groups.save.call_args[0][0]
    assert (saved.name, saved.kind) == ("Transfers", "transfer")
    uow.category_group_budgets.get_by_group_id.assert_not_called()


async def test_rejects_transfer_flip_while_group_has_budgets() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Food & Dining")
    uow.category_groups.get_by_id.return_value = group
    uow.category_group_budgets.get_by_group_id.return_value = [
        make_category_group_budget(group_id=group.id)
    ]
    command = UpdateCategoryGroupCommand(id=group.id, name=group.name, kind="transfer")

    with pytest.raises(ValidationError, match="budgets"):
        await UpdateCategoryGroupUseCase().execute(command, uow)
    uow.category_groups.save.assert_not_called()
