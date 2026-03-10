from src.application.use_cases.seed_category_groups import seed_category_groups
from tests.fixtures.mocks import make_mock_uow


async def test_skips_when_groups_exist() -> None:
    uow = make_mock_uow()
    uow.category_groups.count.return_value = 5

    await seed_category_groups(uow)

    uow.category_groups.save_batch.assert_not_called()
    uow.category_mappings.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_creates_groups_and_mappings_when_empty() -> None:
    uow = make_mock_uow()
    uow.category_groups.count.return_value = 0

    await seed_category_groups(uow)

    uow.category_groups.save_batch.assert_called_once()
    uow.category_mappings.save_batch.assert_called_once()
    uow.commit.assert_called_once()

    groups = uow.category_groups.save_batch.call_args[0][0]
    mappings = uow.category_mappings.save_batch.call_args[0][0]
    assert len(groups) == 16
    assert len(mappings) == 83
