from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from attrs import Attribute

from src.domain.entities.person import Person
from src.domain.exceptions import ValidationError
from src.domain.month_key import MAX_MONTH, assert_month_key

Scope = Literal["household", "personal", "all"]
# Pages with no "all" view: a person-scoped variant of the household page.
PersonScope = Literal["household", "personal"]


def require_person_for_personal_scope(scope: Scope, person_id: UUID | None) -> None:
    """Call from a scoped command's `__attrs_post_init__`."""
    if scope == "personal" and person_id is None:
        raise ValidationError("person_id is required for personal scope")


def person_for_scope(scope: Scope, user: Person) -> UUID | None:
    """The person a scoped request is about: the caller for `personal`,
    nobody for the couple-level scopes. Entry points derive it here so the
    rule guarded by `require_person_for_personal_scope` lives once."""
    return user.id if scope == "personal" else None


def quantize_cents(value: Decimal) -> Decimal:
    """attrs converter — monetary amounts persist as exact cents.

    Guards against float dust arriving via JSON (e.g. a frontend float sum
    of 20.369999999999997), which would keep a month from netting to zero.
    """
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
    if not 1 <= value <= MAX_MONTH:
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


def month_keys(
    _instance: object,
    attribute: Attribute[list[tuple[int, int]]],
    value: list[tuple[int, int]],
) -> None:
    for year, month in value:
        try:
            assert_month_key(year, month)
        except ValueError as e:
            raise ValueError(f"{attribute.name}: {e}") from e
