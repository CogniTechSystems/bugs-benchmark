"""Recurrence rules and their parsing from short text descriptions."""

from dataclasses import dataclass
from datetime import date, timedelta

from scheduler.recurrence import daily, monthly, weekly
from scheduler.weekdays import parse_weekdays, weekday_name

FREQUENCIES = ("daily", "weekly", "monthly")


@dataclass(frozen=True)
class RecurrenceRule:
    """A known frequency with exactly one of an inclusive until date or a positive count, plus an
    interval or weekdays where permitted; violations raise ValueError.
    """

    frequency: str
    interval: int = 1
    weekdays: frozenset[int] = frozenset()
    until: date | None = None
    count: int | None = None

    def __post_init__(self) -> None:
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"Unknown frequency: {self.frequency!r}")
        if (self.until is None) == (self.count is None):
            raise ValueError("A rule needs exactly one of until or count")
        if self.count is not None and self.count < 1:
            raise ValueError("count must be at least 1")
        if self.interval < 1 or (self.interval != 1 and self.frequency != "daily"):
            raise ValueError("interval must be at least 1 and is only valid for daily rules")
        if (self.frequency == "weekly") != bool(self.weekdays):
            raise ValueError("weekdays are required for weekly rules and only allowed there")

    def dates(self, start: date) -> list[date]:
        """Return the rule's occurrence dates on or after start, which opens day and month series,
        stopping at an inclusive until date or after exactly count dates.
        """
        if self.frequency == "daily":
            if self.until is not None:
                return daily(start, self.until, self.interval)
            step = timedelta(days=self.interval)
            return [start + step * index for index in range(self.count or 0)]
        if self.frequency == "weekly":
            if self.until is not None:
                return weekly(start, self.until, set(self.weekdays))
            count = self.count or 0
            return weekly(start, start + timedelta(weeks=count), set(self.weekdays))[:count]
        if self.until is not None:
            months = (self.until.year - start.year) * 12 + self.until.month - start.month + 1
            return [day for day in monthly(start, max(months, 0)) if day <= self.until]
        return monthly(start, self.count or 0)

    def describe(self) -> str:
        """Return the rule as parseable text giving the frequency, then any interval, weekday
        abbreviations, and the until date or count.
        """
        parts = [self.frequency]
        if self.interval != 1:
            parts.append(f"every {self.interval}")
        if self.weekdays:
            names = (weekday_name(day)[:3].lower() for day in sorted(self.weekdays))
            parts.append("on " + ",".join(names))
        if self.until is not None:
            parts.append(f"until {self.until.isoformat()}")
        else:
            parts.append(f"count {self.count}")
        return " ".join(parts)


def parse_rule(text: str) -> RecurrenceRule:
    """Parse case-insensitive text of a frequency followed by distinct key and value options,
    raising ValueError for unknown words, malformed values or invalid combinations.
    """
    words = text.lower().split()
    if not words:
        raise ValueError("A rule cannot be empty")
    frequency, options = words[0], words[1:]
    if len(options) % 2:
        raise ValueError(f"Option without a value in {text!r}")
    values: dict[str, str] = {}
    for key, value in zip(options[::2], options[1::2], strict=True):
        if key in values:
            raise ValueError(f"Repeated option {key!r}")
        values[key] = value
    unknown = set(values) - {"every", "on", "until", "count"}
    if unknown:
        raise ValueError(f"Unknown options: {', '.join(sorted(unknown))}")
    return RecurrenceRule(
        frequency=frequency,
        interval=_parse_int(values.get("every", "1")),
        weekdays=frozenset(parse_weekdays(values["on"])) if "on" in values else frozenset(),
        until=date.fromisoformat(values["until"]) if "until" in values else None,
        count=_parse_int(values["count"]) if "count" in values else None,
    )


def _parse_int(value: str) -> int:
    """Return the text as an integer, raising ValueError unless it consists only of digits."""
    if not value.isdigit():
        raise ValueError(f"Expected a whole number, got {value!r}")
    return int(value)
