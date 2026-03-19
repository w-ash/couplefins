import uuid

from src.application.use_cases.list_unmapped_categories import list_unmapped_categories
from src.domain.entities.category import Category
from tests.fixtures.mocks import make_mock_uow


async def test_returns_unmapped_categories() -> None:
    uow = make_mock_uow()
    uow.categories.get_unmapped.return_value = [
        Category(id=uuid.uuid4(), name="Mystery Category", group_id=None),
        Category(id=uuid.uuid4(), name="Another One", group_id=None),
    ]

    result = await list_unmapped_categories(uow)

    assert result.categories == ["Another One", "Mystery Category"]


async def test_returns_empty_when_all_mapped() -> None:
    uow = make_mock_uow()
    uow.categories.get_unmapped.return_value = []

    result = await list_unmapped_categories(uow)

    assert result.categories == []
