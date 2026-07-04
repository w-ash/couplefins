from pathlib import Path
import re

import pytest

from src.domain.filters import is_reconciliation_relevant
from tests.fixtures.factories import make_transaction

_SRC_DOMAIN_APPLICATION = [
    Path(__file__).resolve().parents[3] / "src" / "domain",
    Path(__file__).resolve().parents[3] / "src" / "application",
]

# Matches the inline `is_excluded`/`is_settlement` boolean-combination forms
# that `is_reconciliation_relevant` replaces, in either operand order, with
# or without the `not` negation. Allows arbitrary whitespace/newlines between
# tokens (e.g. multi-line comprehensions) and requires the same receiver
# (`tx`, `transaction`, ...) on both sides via a backreference.
_INLINE_COPY_PATTERNS = [
    re.compile(r"(\w+)\.is_settlement\s+or\s+\1\.is_excluded"),
    re.compile(r"(\w+)\.is_excluded\s+or\s+\1\.is_settlement"),
    re.compile(r"not\s+(\w+)\.is_excluded\s+and\s+not\s+\1\.is_settlement"),
    re.compile(r"not\s+(\w+)\.is_settlement\s+and\s+not\s+\1\.is_excluded"),
]


@pytest.mark.parametrize(
    ("is_settlement", "is_excluded", "expected"),
    [
        (False, False, True),
        (True, False, False),
        (False, True, False),
        (True, True, False),
    ],
)
def test_is_reconciliation_relevant_truth_table(
    is_settlement: bool, is_excluded: bool, expected: bool
) -> None:
    tx = make_transaction(is_settlement=is_settlement, is_excluded=is_excluded)
    assert is_reconciliation_relevant(tx) is expected


def test_no_inline_copies_of_the_exclusion_predicate() -> None:
    """Grep gate: `is_reconciliation_relevant` is the single source of truth.

    Fails if any file under src/domain or src/application (other than
    filters.py itself) hand-copies the `is_excluded`/`is_settlement` boolean
    combination instead of calling the shared predicate. Does not flag the
    legitimate SQL-layer filters (`TransactionModel.is_settlement.is_(False)`,
    `postgresql_where=text("NOT is_settlement")`) since those don't match
    the Python attribute-access boolean forms above.
    """
    offenders: list[str] = []
    for root in _SRC_DOMAIN_APPLICATION:
        for path in root.rglob("*.py"):
            if path.name == "filters.py":
                continue
            text = path.read_text()
            for pattern in _INLINE_COPY_PATTERNS:
                if pattern.search(text):
                    offenders.append(str(path))
                    break

    assert offenders == [], (
        "Inline copies of the is_excluded/is_settlement predicate found — "
        f"use is_reconciliation_relevant() instead: {offenders}"
    )
