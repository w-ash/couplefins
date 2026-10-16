import pytest

from src.domain.parsing.depositor import match_depositor
from tests.fixtures.factories import ALICE, BOB, make_person

COUPLE = (ALICE, BOB)


@pytest.mark.parametrize(
    "texts",
    [
        ("Online Transfer from ALICE", "", ""),
        ("Deposit", "ZELLE FROM alice SMITH", ""),
        ("Deposit", "", "Alice's paycheck share"),
    ],
)
def test_one_name_in_any_text_names_the_depositor(texts: tuple[str, ...]) -> None:
    assert match_depositor(texts, COUPLE) == ALICE.id


def test_no_name_names_no_depositor() -> None:
    assert match_depositor(("Interest payment", "INTEREST", ""), COUPLE) is None


def test_both_names_name_no_depositor() -> None:
    assert match_depositor(("Transfer Alice to Bob", "", ""), COUPLE) is None


def test_a_name_inside_a_longer_word_does_not_match() -> None:
    assert match_depositor(("BOBCAT RENTALS REFUND", "", ""), COUPLE) is None


def test_a_blank_name_never_matches() -> None:
    blank = make_person(name=" ")

    assert match_depositor(("Deposit from Bob", "", ""), (blank, BOB)) == BOB.id
