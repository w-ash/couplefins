from src.application.use_cases.create_category_group import (
    CreateCategoryGroupCommand,
    CreateCategoryGroupUseCase,
)
from tests.fixtures.mocks import make_mock_uow


async def test_creates_group_and_commits() -> None:
    uow = make_mock_uow()
    command = CreateCategoryGroupCommand(name="New Group")

    await CreateCategoryGroupUseCase(uow).execute(command)

    uow.category_groups.save.assert_called_once()
    saved = uow.category_groups.save.call_args[0][0]
    assert saved.name == "New Group"
    uow.commit.assert_called_once()
