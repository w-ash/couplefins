"""Calendar month keys — the (year, month) pairs settlement math runs on."""

MAX_MONTH = 12

type MonthKey = tuple[int, int]


def assert_month_key(year: int, month: int) -> None:
    """Reject an out-of-range (year, month) pair. Single source of truth."""
    if year < 1:
        raise ValueError(f"year must be >= 1, got {year}")
    if not 1 <= month <= MAX_MONTH:
        raise ValueError(f"month must be 1-{MAX_MONTH}, got {month}")
