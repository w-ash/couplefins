from decimal import Decimal

from attrs import Attribute

_MAX_MONTH = 12


def non_empty_string(_instance: object, attribute: Attribute[str], value: str) -> None:
    if not value.strip():
        raise ValueError(f"{attribute.name} must not be empty")


def positive_int(_instance: object, attribute: Attribute[int], value: int) -> None:
    if value <= 0:
        raise ValueError(f"{attribute.name} must be positive, got {value}")


def positive_decimal(
    _instance: object, attribute: Attribute[Decimal], value: Decimal
) -> None:
    if value <= 0:
        raise ValueError(f"{attribute.name} must be positive, got {value}")


def month_range(_instance: object, attribute: Attribute[int], value: int) -> None:
    if not 1 <= value <= _MAX_MONTH:
        raise ValueError(f"{attribute.name} must be 1-12, got {value}")
