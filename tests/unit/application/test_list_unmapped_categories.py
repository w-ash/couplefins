from src.application.use_cases.list_unmapped_categories import list_unmapped_categories
from tests.fixtures.factories import make_category_mapping
from tests.fixtures.mocks import make_mock_uow


async def test_returns_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.transactions.get_distinct_categories.return_value = [
        "Groceries",
        "Dining Out",
        "Mystery Category",
    ]
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Dining Out"),
    ]

    result = await list_unmapped_categories(uow)

    assert result == ["Mystery Category"]


async def test_returns_empty_when_all_mapped() -> None:
    uow = make_mock_uow()
    uow.transactions.get_distinct_categories.return_value = ["Groceries"]
    uow.category_mappings.get_all.return_value = [
        make_category_mapping(category="Groceries"),
    ]

    result = await list_unmapped_categories(uow)

    assert result == []


async def test_returns_empty_when_no_transactions() -> None:
    uow = make_mock_uow()
    uow.transactions.get_distinct_categories.return_value = []
    uow.category_mappings.get_all.return_value = []

    result = await list_unmapped_categories(uow)

    assert result == []
