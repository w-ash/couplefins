from decimal import Decimal

from attrs import Attribute

_MAX_MONTH = 12


def non_empty_string(_instance: object, attribute: Attribute[str], value: str) -> None:
    if not value.strip():
        raise ValueError(f"{attribute.name} must not be empty")


def positive_int(_instance: object, attribute: Attribute[int], value: int) -> None:
    if value <= 0:
        raise ValueError(f"{attribute.name} must be positive, got {value}")


def assert_positive_decimal(value: Decimal, label: str = "amount") -> Decimal:
    """Reusable check for both attrs validators and Pydantic field_validators."""
    if value <= 0:
        raise ValueError(f"{label} must be positive")
    return value


def positive_decimal(
    _instance: object, attribute: Attribute[Decimal], value: Decimal
) -> None:
    assert_positive_decimal(value, attribute.name)


def month_range(_instance: object, attribute: Attribute[int], value: int) -> None:
    if not 1 <= value <= _MAX_MONTH:
        raise ValueError(f"{attribute.name} must be 1-12, got {value}")


def optional_month_range(
    _instance: object, attribute: Attribute[int | None], value: int | None
) -> None:
    if value is not None:
        month_range(_instance, attribute, value)  # type: ignore[arg-type]


def optional_positive_int(
    _instance: object, attribute: Attribute[int | None], value: int | None
) -> None:
    if value is not None:
        positive_int(_instance, attribute, value)  # type: ignore[arg-type]
