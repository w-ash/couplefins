from src.domain.categories import get_category_kinds, get_non_spending_categories
from tests.fixtures.factories import make_category, make_category_group


def test_non_spending_categories_follow_their_group_kind() -> None:
    transfer = make_category_group(name="Transfer", kind="transfer")
    income = make_category_group(name="Income", kind="income")
    food = make_category_group(name="Food & Dining")
    categories = [
        make_category(name="Credit Card Payment", group_id=transfer.id),
        make_category(name="Transfer", group_id=transfer.id),
        make_category(name="Paychecks", group_id=income.id),
        make_category(name="Dining Out", group_id=food.id),
        make_category(name="Mystery", group_id=None),
    ]
    groups = [transfer, income, food]

    assert get_non_spending_categories(categories, groups) == {
        "Credit Card Payment",
        "Transfer",
        "Paychecks",
    }
    assert get_category_kinds(categories, groups) == {
        "Credit Card Payment": "transfer",
        "Transfer": "transfer",
        "Paychecks": "income",
        "Dining Out": "expense",
    }


def test_only_spending_groups_gives_empty_set() -> None:
    food = make_category_group(name="Food & Dining")
    categories = [make_category(name="Dining Out", group_id=food.id)]
    assert get_non_spending_categories(categories, [food]) == frozenset()
