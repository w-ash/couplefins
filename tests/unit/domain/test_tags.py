import pytest

from src.domain.tags import (
    has_tag_prefix,
    is_namespaced_tag,
    is_tag_namespace,
    merge_namespaced_tags,
    namespaced_tags,
    tag_value,
)


@pytest.mark.parametrize(
    ("tag", "namespaced"),
    [
        ("line:mortgage", True),
        ("pot:renovation", True),
        ("source:gift", True),
        ("share:closing", True),
        ("loan:2nd-lien", True),
        ("line:home loan", True),
        ("pot:bills_2026", True),
        ("line:v1.2", True),
        ("shared", False),
        ("s50", False),
        ("line:", False),
        (":mortgage", False),
        ("line: mortgage", False),
        ("line:.mortgage", False),
        ("line:_mortgage", False),
        ("line:mortgage/2", False),
        ("Line:Mortgage", False),
        ("1x:y", False),
        ("line:mortgage\n", False),
    ],
)
def test_namespaced_tag_grammar(tag: str, namespaced: bool) -> None:
    assert is_namespaced_tag(tag) is namespaced


@pytest.mark.parametrize(
    ("prefix", "namespace"),
    [
        ("line:", True),
        ("pot-a:", True),
        ("line", False),
        ("line:mortgage", False),
        (":", False),
        ("Line:", False),
        ("", False),
    ],
)
def test_tag_namespace_grammar(prefix: str, namespace: bool) -> None:
    assert is_tag_namespace(prefix) is namespace


def test_namespaced_tags_keep_their_order() -> None:
    assert namespaced_tags(("shared", "pot:bills", "s50", "line:mortgage")) == (
        "pot:bills",
        "line:mortgage",
    )


def test_merge_appends_stored_labels_the_source_lacks() -> None:
    merged = merge_namespaced_tags(
        incoming=("shared", "line:repair"),
        existing=("pot:bills", "discuss", "line:repair", "line:mortgage"),
    )

    assert merged == ("shared", "line:repair", "pot:bills", "line:mortgage")


def test_merge_never_restores_a_plain_tag() -> None:
    assert merge_namespaced_tags(("shared",), ("shared", "discuss")) == ("shared",)


def test_merge_leaves_the_incoming_tags_as_they_are() -> None:
    assert merge_namespaced_tags(("shared", "shared"), ("pot:a", "pot:a")) == (
        "shared",
        "shared",
        "pot:a",
    )


def test_prefix_matches_a_tag_with_a_value_in_the_namespace() -> None:
    assert has_tag_prefix(("shared", "line:mortgage"), "line:")
    assert not has_tag_prefix(("shared", "pot:line"), "line:")
    assert not has_tag_prefix(("line:",), "line:")


def test_tag_value_is_the_first_match() -> None:
    tags = ("shared", "line:", "line:repair", "line:renovation")

    assert tag_value(tags, "line:") == "repair"
    assert tag_value(tags, "pot:") is None
