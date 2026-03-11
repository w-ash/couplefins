from src.application.use_cases._shared.transactions import (
    find_all_unmapped_categories,
    find_new_categories,
    find_unmapped_categories,
)
from tests.fixtures.factories import make_category_mapping


def test_find_new_categories_returns_unknown() -> None:
    mappings = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_new_categories(mappings, tx_cats) == ["Mystery"]


def test_find_new_categories_empty_when_all_known() -> None:
    mappings = [make_category_mapping(category="Groceries")]
    assert find_new_categories(mappings, {"Groceries"}) == []


def test_find_new_categories_ignores_unmapped_in_db() -> None:
    mappings = [make_category_mapping(category="Groceries", group_id=None)]
    assert find_new_categories(mappings, {"Groceries"}) == []


def test_find_unmapped_categories_returns_null_group() -> None:
    mappings = [
        make_category_mapping(category="Groceries", group_id=None),
        make_category_mapping(category="Gas"),
    ]
    tx_cats = {"Groceries", "Gas"}
    assert find_unmapped_categories(mappings, tx_cats) == ["Groceries"]


def test_find_unmapped_categories_empty_when_all_mapped() -> None:
    mappings = [make_category_mapping(category="Groceries")]
    assert find_unmapped_categories(mappings, {"Groceries"}) == []


def test_find_unmapped_categories_ignores_absent_categories() -> None:
    mappings = [make_category_mapping(category="Groceries", group_id=None)]
    assert find_unmapped_categories(mappings, {"Gas"}) == []


def test_find_all_unmapped_categories_combines_new_and_unmapped() -> None:
    mappings = [
        make_category_mapping(category="Groceries", group_id=None),
        make_category_mapping(category="Gas"),
    ]
    tx_cats = {"Groceries", "Gas", "Mystery"}
    assert find_all_unmapped_categories(mappings, tx_cats) == ["Groceries", "Mystery"]


def test_find_all_unmapped_categories_empty_when_all_mapped() -> None:
    mappings = [
        make_category_mapping(category="Groceries"),
        make_category_mapping(category="Gas"),
    ]
    assert find_all_unmapped_categories(mappings, {"Groceries", "Gas"}) == []
