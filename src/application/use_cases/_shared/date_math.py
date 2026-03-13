import calendar
from datetime import date


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def detect_single_month(start: date, end: date) -> tuple[int, int] | None:
    if start.day != 1:
        return None
    last_day = calendar.monthrange(start.year, start.month)[1]
    if end == date(start.year, start.month, last_day):
        return (start.year, start.month)
    return None
