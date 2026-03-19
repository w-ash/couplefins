import pytest

from src.application.use_cases.bulk_update_mappings import (
    BulkUpdateMappingsCommand,
    BulkUpdateMappingsUseCase,
    MappingEntry,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_category, make_category_group
from tests.fixtures.mocks import make_mock_uow


async def test_saves_mappings_and_commits() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    uow.categories.get_all.return_value = []
    command = BulkUpdateMappingsCommand(
        mappings=[MappingEntry(category="Groceries", group_id=group.id)]
    )

    result = await BulkUpdateMappingsUseCase().execute(command, uow)

    assert result.updated_count == 1
    uow.categories.save_batch.assert_called_once()
    saved = uow.categories.save_batch.call_args[0][0]
    assert len(saved) == 1
    assert saved[0].name == "Groceries"
    assert saved[0].group_id == group.id
    uow.commit.assert_called_once()


async def test_uses_evolve_for_existing_categories() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    existing = make_category(
        name="Groceries", group_id=make_category_group().id, include_personal=True
    )
    uow.category_groups.get_by_id.return_value = group
    uow.categories.get_all.return_value = [existing]
    command = BulkUpdateMappingsCommand(
        mappings=[MappingEntry(category="Groceries", group_id=group.id)]
    )

    await BulkUpdateMappingsUseCase().execute(command, uow)

    saved = uow.categories.save_batch.call_args[0][0]
    assert saved[0].id == existing.id
    assert saved[0].group_id == group.id
    assert saved[0].include_personal is True  # preserved via evolve


async def test_raises_validation_error_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = BulkUpdateMappingsCommand(
        mappings=[MappingEntry(category="Groceries", group_id=make_category_group().id)]
    )

    with pytest.raises(ValidationError):
        await BulkUpdateMappingsUseCase().execute(command, uow)
