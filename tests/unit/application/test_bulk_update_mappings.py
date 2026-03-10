import pytest

from src.application.use_cases.bulk_update_mappings import (
    BulkUpdateMappingsCommand,
    BulkUpdateMappingsUseCase,
    MappingEntry,
)
from src.domain.exceptions import ValidationError
from tests.fixtures.factories import make_category_group
from tests.fixtures.mocks import make_mock_uow


async def test_saves_mappings_and_commits() -> None:
    uow = make_mock_uow()
    group = make_category_group()
    uow.category_groups.get_by_id.return_value = group
    command = BulkUpdateMappingsCommand(
        mappings=[MappingEntry(category="Groceries", group_id=group.id)]
    )

    result = await BulkUpdateMappingsUseCase().execute(command, uow)

    assert result.updated_count == 1
    uow.category_mappings.save_batch.assert_called_once()
    uow.commit.assert_called_once()


async def test_raises_validation_error_for_missing_group() -> None:
    uow = make_mock_uow()
    uow.category_groups.get_by_id.return_value = None
    command = BulkUpdateMappingsCommand(
        mappings=[MappingEntry(category="Groceries", group_id=make_category_group().id)]
    )

    with pytest.raises(ValidationError):
        await BulkUpdateMappingsUseCase().execute(command, uow)
