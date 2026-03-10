from src.application.use_cases.list_category_groups import list_category_groups
from tests.fixtures.factories import make_category_group, make_category_mapping
from tests.fixtures.mocks import make_mock_uow


async def test_returns_groups_with_mappings() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Food & Dining")
    mapping = make_category_mapping(category="Groceries", group_id=group.id)
    uow.category_groups.get_all.return_value = [group]
    uow.category_mappings.get_all.return_value = [mapping]

    result = await list_category_groups(uow)

    assert len(result.items) == 1
    assert result.items[0].group == group
    assert result.items[0].mappings == [mapping]


async def test_returns_empty_mappings_for_group_without_categories() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Empty Group")
    uow.category_groups.get_all.return_value = [group]
    uow.category_mappings.get_all.return_value = []

    result = await list_category_groups(uow)

    assert len(result.items) == 1
    assert result.items[0].mappings == []
