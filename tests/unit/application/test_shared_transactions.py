import uuid

from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
    find_new_categories,
    find_unmapped_categories,
)
from src.domain.entities.category import Category
from tests.fixtures.factories import make_category


def test_find_new_categories_returns_unknown() -> None:
    categories = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_new_categories(categories, tx_cats) == ["Mystery"]


def test_find_new_categories_empty_when_all_known() -> None:
    categories = [make_category(name="Groceries")]
    assert find_new_categories(categories, {"Groceries"}) == []


def test_find_new_categories_ignores_unmapped_in_db() -> None:
    categories = [Category(id=uuid.uuid4(), name="Groceries", group_id=None)]
    assert find_new_categories(categories, {"Groceries"}) == []


def test_find_unmapped_categories_returns_null_group() -> None:
    categories = [
        Category(id=uuid.uuid4(), name="Groceries", group_id=None),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas"}
    assert find_unmapped_categories(categories, tx_cats) == ["Groceries"]


def test_find_unmapped_categories_empty_when_all_mapped() -> None:
    categories = [make_category(name="Groceries")]
    assert find_unmapped_categories(categories, {"Groceries"}) == []


def test_find_unmapped_categories_ignores_absent_categories() -> None:
    categories = [Category(id=uuid.uuid4(), name="Groceries", group_id=None)]
    assert find_unmapped_categories(categories, {"Gas"}) == []


def test_find_all_unmapped_categories_combines_new_and_unmapped() -> None:
    categories = [
        Category(id=uuid.uuid4(), name="Groceries", group_id=None),
        make_category(name="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_all_unmapped_categories(categories, tx_cats) == ["Groceries", "Mystery"]


def test_find_all_unmapped_categories_empty_when_all_mapped() -> None:
    categories = [
        make_category(name="Groceries"),
        make_category(name="Gas"),
    ]
    assert find_all_unmapped_categories(categories, {"Groceries", "Gas"}) == []
