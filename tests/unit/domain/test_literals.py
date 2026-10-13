import pytest

from src.domain.entities.account import ACCOUNT_KINDS
from src.domain.literals import parse_literal


def test_parse_literal_returns_an_allowed_value() -> None:
    assert parse_literal("joint", ACCOUNT_KINDS, "account kind") == "joint"


def test_parse_literal_rejects_an_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unknown account kind: 'shared'"):
        parse_literal("shared", ACCOUNT_KINDS, "account kind")
