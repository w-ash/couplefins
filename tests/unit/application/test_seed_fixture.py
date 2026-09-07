import json
from pathlib import Path
import re

from pydantic import TypeAdapter
import pytest

from src.application.use_cases.seed_category_groups import (
    DEFAULT_FIXTURE_PATH,
    LOCAL_FIXTURE_PATH,
    _CategoryGroupFixture,
    _fixture_path,
)

_adapter = TypeAdapter(list[_CategoryGroupFixture])
_ICON_REGISTRY = Path("web/src/lib/category-icons.ts")


def test_default_fixture_is_valid() -> None:
    # This file is the only taxonomy a fresh database has; a malformed one
    # would crash startup, which is the hardest place to debug it.
    groups = _adapter.validate_json(DEFAULT_FIXTURE_PATH.read_bytes())
    assert len(groups) > 0
    assert all(group["categories"] for group in groups)


def test_default_fixture_group_names_are_unique() -> None:
    groups = _adapter.validate_json(DEFAULT_FIXTURE_PATH.read_bytes())
    names = [group["name"] for group in groups]
    assert len(names) == len(set(names))


def test_default_fixture_declares_income_and_transfer_kinds() -> None:
    # Both kinds must exist from the start, or a new household's paychecks and
    # card payments would count as spending until someone noticed.
    groups = _adapter.validate_json(DEFAULT_FIXTURE_PATH.read_bytes())
    kinds = {group.get("kind", "expense") for group in groups}
    assert {"income", "transfer"} <= kinds


def test_default_fixture_icons_exist_in_the_frontend_registry() -> None:
    # getCategoryGroupIcon falls back to a generic tag for an unknown name, so
    # a typo here degrades silently in the UI rather than failing anywhere.
    registered = set(
        re.findall(
            r'^ {2}"?([a-z-]+)"?:',
            _ICON_REGISTRY.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    icons = {
        group["icon"]
        for group in _adapter.validate_json(DEFAULT_FIXTURE_PATH.read_bytes())
    }
    assert icons <= registered


def test_default_fixture_carries_no_household_specific_categories() -> None:
    # The committed default is generic on purpose: the couple's own taxonomy
    # lives in the gitignored local override, not in a public repository.
    text = json.dumps(
        json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    ).lower()
    for personal in ("playa", "festival", "burning", "reimbursable"):
        assert personal not in text


def test_local_override_wins_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.application.use_cases.seed_category_groups.LOCAL_FIXTURE_PATH",
        DEFAULT_FIXTURE_PATH,  # any path that exists
    )
    assert _fixture_path() == DEFAULT_FIXTURE_PATH


def test_default_is_used_when_no_local_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The deployed container has no data/ directory at all.
    monkeypatch.setattr(
        "src.application.use_cases.seed_category_groups.LOCAL_FIXTURE_PATH",
        tmp_path / "absent.json",
    )
    assert _fixture_path() == DEFAULT_FIXTURE_PATH


def test_local_override_is_not_committed() -> None:
    # A regression here would publish the household's taxonomy.
    assert LOCAL_FIXTURE_PATH.name == "category_groups.json"
    assert LOCAL_FIXTURE_PATH.parent.name == "data"
