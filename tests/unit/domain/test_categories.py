from src.domain.categories import get_transfer_categories
from tests.fixtures.factories import make_category, make_category_group


def test_transfer_categories_follow_their_group_kind() -> None:
    transfer = make_category_group(name="Transfer", kind="transfer")
    food = make_category_group(name="Food & Dining")
    categories = [
        make_category(name="Credit Card Payment", group_id=transfer.id),
        make_category(name="Transfer", group_id=transfer.id),
        make_category(name="Dining Out", group_id=food.id),
        make_category(name="Mystery", group_id=None),
    ]

    assert get_transfer_categories(categories, [transfer, food]) == {
        "Credit Card Payment",
        "Transfer",
    }


def test_no_transfer_groups_gives_empty_set() -> None:
    food = make_category_group(name="Food & Dining")
    categories = [make_category(name="Dining Out", group_id=food.id)]
    assert get_transfer_categories(categories, [food]) == frozenset()
