import calendar
from datetime import date

from src.domain.month_key import shift_month


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def add_months(day: date, months: int) -> date:
    """The same day `months` months later (earlier when negative). A day
    past the end of the target month becomes its last day: January 31
    plus one month is February 28 or 29."""
    year, month = shift_month((day.year, day.month), months)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
