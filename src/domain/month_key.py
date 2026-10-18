"""Calendar month keys — the (year, month) pairs settlement math runs on."""

MAX_MONTH = 12

type MonthKey = tuple[int, int]


def assert_month_key(year: int, month: int) -> None:
    """Reject an out-of-range (year, month) pair. Single source of truth."""
    if year < 1:
        raise ValueError(f"year must be >= 1, got {year}")
    if not 1 <= month <= MAX_MONTH:
        raise ValueError(f"month must be 1-{MAX_MONTH}, got {month}")


def shift_month(key: MonthKey, months: int) -> MonthKey:
    """The month `months` months after `key` (before it when negative)."""
    year, month = key
    shifted_year, shifted_index = divmod(
        year * MAX_MONTH + month - 1 + months, MAX_MONTH
    )
    return shifted_year, shifted_index + 1


def months_through(start: MonthKey, end: MonthKey) -> tuple[MonthKey, ...]:
    """Every month from `start` through `end`, ascending. Empty when `start`
    is after `end`."""
    months: list[MonthKey] = []
    key = start
    while key <= end:
        months.append(key)
        key = shift_month(key, 1)
    return tuple(months)
