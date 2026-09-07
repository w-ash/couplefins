from src.application.use_cases.seed_category_groups import seed_category_groups
from tests.fixtures.mocks import make_mock_uow


async def test_skips_when_groups_exist() -> None:
    uow = make_mock_uow()
    uow.category_groups.count.return_value = 5

    await seed_category_groups(uow)

    uow.category_groups.save_batch.assert_not_called()
    uow.categories.save_batch.assert_not_called()
    uow.commit.assert_not_called()


async def test_creates_groups_and_categories_when_empty() -> None:
    uow = make_mock_uow()
    uow.category_groups.count.return_value = 0

    await seed_category_groups(uow)

    uow.category_groups.save_batch.assert_called_once()
    uow.categories.save_batch.assert_called_once()
    uow.commit.assert_called_once()

    groups = uow.category_groups.save_batch.call_args[0][0]
    categories = uow.categories.save_batch.call_args[0][0]
    assert len(groups) == 15
    assert len(categories) == 77


async def test_seed_marks_only_the_transfer_group_as_transfer() -> None:
    uow = make_mock_uow()
    uow.category_groups.count.return_value = 0

    await seed_category_groups(uow)

    groups = uow.category_groups.save_batch.call_args[0][0]
    assert {g.name for g in groups if g.kind == "transfer"} == {"Transfers"}
