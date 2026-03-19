from src.application.use_cases.list_category_groups import list_category_groups
from tests.fixtures.factories import make_category, make_category_group
from tests.fixtures.mocks import make_mock_uow


async def test_returns_groups_with_categories() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Food & Dining")
    category = make_category(name="Groceries", group_id=group.id)
    uow.category_groups.get_all.return_value = [group]
    uow.categories.get_all.return_value = [category]

    result = await list_category_groups(uow)

    assert len(result.items) == 1
    assert result.items[0].group == group
    assert result.items[0].categories == [category]


async def test_returns_empty_categories_for_group_without_categories() -> None:
    uow = make_mock_uow()
    group = make_category_group(name="Empty Group")
    uow.category_groups.get_all.return_value = [group]
    uow.categories.get_all.return_value = []

    result = await list_category_groups(uow)

    assert len(result.items) == 1
    assert result.items[0].categories == []
