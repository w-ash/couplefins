"""Calendar month keys — the (year, month) pairs settlement math runs on."""

MAX_MONTH = 12

type MonthKey = tuple[int, int]


def assert_month_key(year: int, month: int) -> None:
    """Reject an out-of-range (year, month) pair. Single source of truth."""
    if year < 1:
        raise ValueError(f"year must be >= 1, got {year}")
    if not 1 <= month <= MAX_MONTH:
        raise ValueError(f"month must be 1-{MAX_MONTH}, got {month}")


def months_through(start: MonthKey, end: MonthKey) -> tuple[MonthKey, ...]:
    """Every month from `start` through `end`, ascending. Empty when `start`
    is after `end`."""
    months: list[MonthKey] = []
    year, month = start
    while (year, month) <= end:
        months.append((year, month))
        year, month = (year + 1, 1) if month == MAX_MONTH else (year, month + 1)
    return tuple(months)
