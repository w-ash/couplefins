from datetime import date
from decimal import Decimal

type FieldValue = date | Decimal | str | int | tuple[str, ...] | None


def field_str(value: FieldValue) -> str:
    """Canonical string representation for audit edit values."""
    if isinstance(value, tuple):
        return ",".join(value)
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else str(value)
