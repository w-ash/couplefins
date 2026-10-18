from datetime import date

import pytest

from src.domain.date_math import add_months
from src.domain.month_key import MonthKey, shift_month


@pytest.mark.parametrize(
    ("key", "months", "expected"),
    [
        ((2026, 1), 1, (2026, 2)),
        ((2026, 12), 1, (2027, 1)),
        ((2026, 1), -1, (2025, 12)),
        ((2026, 5), 0, (2026, 5)),
        ((2026, 11), 15, (2028, 2)),
    ],
)
def test_shift_month_steps_across_years(
    key: MonthKey, months: int, expected: MonthKey
) -> None:
    assert shift_month(key, months) == expected


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 1, 15), 1, date(2026, 2, 15)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 11, 30), 3, date(2027, 2, 28)),
        (date(2026, 12, 1), 1, date(2027, 1, 1)),
        (date(2026, 3, 31), -1, date(2026, 2, 28)),
        (date(2026, 5, 1), 0, date(2026, 5, 1)),
    ],
)
def test_add_months_keeps_the_day_or_clamps_to_the_months_end(
    day: date, months: int, expected: date
) -> None:
    assert add_months(day, months) == expected
