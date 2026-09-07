import pytest

from src.application.use_cases import seed_category_groups


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.fspath)
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def seed_from_the_committed_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seed the taxonomy every environment has, never a laptop's own.

    `data/category_groups.json` is gitignored and present only on the
    couple's machines, where it takes precedence. Left alone, the suite would
    assert against one taxonomy locally and another in CI.
    """
    monkeypatch.setattr(
        seed_category_groups,
        "LOCAL_FIXTURE_PATH",
        seed_category_groups.LOCAL_FIXTURE_PATH.with_name("absent.json"),
    )
