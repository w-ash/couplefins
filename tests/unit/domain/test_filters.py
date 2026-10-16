from decimal import Decimal
from pathlib import Path
import re

from attrs import evolve
import pytest

from src.domain.exceptions import InvariantViolationError
from src.domain.filters import (
    depositor_of,
    exclude_non_spending,
    is_joint_row,
    is_reconciliation_relevant,
    is_split_relevant,
    payer_of,
)
from tests.fixtures.factories import ALICE, make_transaction

_SRC = Path(__file__).resolve().parents[3] / "src"
_SRC_DOMAIN_APPLICATION = [_SRC / "domain", _SRC / "application"]
# A missing payer, spelled out instead of asking `is_joint_row`.
_INLINE_JOINT_CHECK = re.compile(r"payer_person_id\s+is\s+(not\s+)?None")

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


def test_exclude_non_spending_drops_both_legs_and_keeps_the_rest() -> None:
    debit = make_transaction(category="Credit Card Payment", amount=Decimal(-500))
    credit = make_transaction(category="Credit Card Payment", amount=Decimal(500))
    dinner = make_transaction(category="Dining Out")

    assert exclude_non_spending([debit, credit, dinner], {"Credit Card Payment"}) == [
        dinner
    ]


def test_exclude_non_spending_is_exact_match() -> None:
    tx = make_transaction(category="Credit Card Payments")
    assert exclude_non_spending([tx], {"Credit Card Payment"}) == [tx]


def test_exclude_non_spending_empty_set_is_a_no_op() -> None:
    txs = [make_transaction(category="Credit Card Payment")]
    assert exclude_non_spending(txs, frozenset()) is txs


def test_joint_row_is_never_split_relevant_even_when_split() -> None:
    joint = make_transaction(joint=True)

    assert is_joint_row(joint)
    assert not is_split_relevant(joint)
    assert not is_split_relevant(evolve(joint, payer_percentage=50))
    assert is_split_relevant(make_transaction(payer_percentage=50))


def test_payer_of_a_personal_row_is_its_payer() -> None:
    assert payer_of(make_transaction(payer_person_id=ALICE.id)) == ALICE.id


def test_payer_of_a_joint_row_is_an_invariant_violation() -> None:
    with pytest.raises(InvariantViolationError, match="joint"):
        payer_of(make_transaction(joint=True))


def test_depositor_of_is_the_depositor_of_money_into_a_joint_account() -> None:
    deposit = make_transaction(
        joint=True, amount=Decimal(1500), depositor_person_id=ALICE.id
    )

    assert depositor_of(deposit) == ALICE.id
    assert depositor_of(evolve(deposit, amount=Decimal(-1500))) is None
    assert depositor_of(evolve(deposit, depositor_person_id=None)) is None
    assert depositor_of(make_transaction(amount=Decimal(1500))) is None


def test_no_inline_copies_of_the_joint_row_check() -> None:
    """Grep gate: `is_joint_row` and `payer_of` (filters.py), and the
    entity's own `is_joint_payer` (split_rules.py), are the only places
    under src/ that test for a missing payer. SQL filters
    (`payer_person_id.is_(None)`) and constraint text are not matched."""
    allowed = {_SRC / "domain" / "filters.py", _SRC / "domain" / "split_rules.py"}
    offenders = [
        str(path)
        for path in _SRC.rglob("*.py")
        if path not in allowed and _INLINE_JOINT_CHECK.search(path.read_text())
    ]

    assert offenders == [], (
        f"Inline joint-row checks found — use is_joint_row(): {offenders}"
    )
