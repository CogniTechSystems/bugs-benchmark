"""Generation of recurring event dates in ascending calendar order."""

import calendar
from datetime import date, timedelta


def add_months(day: date, months: int) -> date:
    """Return the date moved by the given number of calendar months, possibly negative, clamping the
    day of the month to the target month's last day.
    """
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def daily(start: date, end: date, interval: int = 1) -> list[date]:
    """Return every interval-th date from start up to and including end, empty when end precedes
    start; an interval below one raises ValueError.
    """
    if interval < 1:
        raise ValueError("interval must be at least 1")
    dates = []
    current = start
    while current < end:
        dates.append(current)
        current += timedelta(days=interval)
    return dates


def weekly(start: date, end: date, weekdays: set[int]) -> list[date]:
    """Return the dates from start to end inclusive whose weekday, numbered from Monday as zero, is
    in the set; empty or invalid sets raise ValueError.
    """
    if not weekdays or not weekdays <= set(range(7)):
        raise ValueError("weekdays must contain values from 0 (Monday) to 6 (Sunday)")
    dates = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        if day.isoweekday() in weekdays:
            dates.append(day)
    return dates


def monthly(start: date, occurrences: int) -> list[date]:
    """Return the requested number of dates a calendar month apart from start, each keeping its day
    of the month, clamped in shorter months; negatives raise ValueError.
    """
    if occurrences < 0:
        raise ValueError("occurrences cannot be negative")
    dates = [start] if occurrences else []
    while len(dates) < occurrences:
        dates.append(add_months(dates[-1], 1))
    return dates
