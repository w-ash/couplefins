from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from uuid import UUID

type FieldValue = (
    date | Decimal | str | int | UUID | tuple[str, ...] | Mapping[UUID, int] | None
)


def field_str(value: FieldValue) -> str:
    """Canonical string representation for audit edit values.

    A mapping of owner shares renders as `<id>:<percent>` pairs, by id.
    """
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, Mapping):
        return ",".join(f"{k}:{value[k]}" for k in sorted(value, key=str))
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else str(value)
