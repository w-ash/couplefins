import pytest

from src.domain.auth import validate_password_strength
from src.domain.exceptions import ValidationError


def test_accepts_valid_password() -> None:
    validate_password_strength("securepass123")


def test_accepts_exactly_min_length() -> None:
    validate_password_strength("12345678")


def test_rejects_too_short() -> None:
    with pytest.raises(ValidationError, match="at least 8"):
        validate_password_strength("short")


def test_rejects_empty() -> None:
    with pytest.raises(ValidationError, match="at least 8"):
        validate_password_strength("")


def test_rejects_seven_chars() -> None:
    with pytest.raises(ValidationError, match="at least 8"):
        validate_password_strength("1234567")
