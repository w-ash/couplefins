from src.application.use_cases.get_tags import GetTagsUseCase
from tests.fixtures.mocks import make_mock_uow


class TestGetTags:
    async def test_returns_distinct_tags(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_distinct_tags.return_value = ["s50", "shared"]

        result = await GetTagsUseCase().execute(uow)

        assert result.tags == ["s50", "shared"]
        uow.transactions.get_distinct_tags.assert_called_once()

    async def test_returns_empty_list_when_no_tags(self) -> None:
        uow = make_mock_uow()
        uow.transactions.get_distinct_tags.return_value = []

        result = await GetTagsUseCase().execute(uow)

        assert result.tags == []
