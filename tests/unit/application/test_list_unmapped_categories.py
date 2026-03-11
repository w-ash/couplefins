from src.application.use_cases.list_unmapped_categories import list_unmapped_categories
from tests.fixtures.factories import make_category_mapping
from tests.fixtures.mocks import make_mock_uow


async def test_returns_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.category_mappings.get_unmapped.return_value = [
        make_category_mapping(category="Mystery Category", group_id=None),
        make_category_mapping(category="Another One", group_id=None),
    ]

    result = await list_unmapped_categories(uow)

    assert result.categories == ["Another One", "Mystery Category"]


async def test_returns_empty_when_all_mapped() -> None:
    uow = make_mock_uow()
    uow.category_mappings.get_unmapped.return_value = []

    result = await list_unmapped_categories(uow)

    assert result.categories == []
