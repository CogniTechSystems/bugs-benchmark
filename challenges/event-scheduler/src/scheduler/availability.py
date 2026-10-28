"""Working hours and the search for free time on an agenda."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from scheduler.agenda import Agenda
from scheduler.slots import Slot
from scheduler.weekdays import WORKDAYS


@dataclass(frozen=True)
class WorkingHours:
    """A booking window from start up to but excluding end on weekdays numbered from Monday as zero,
    Monday to Friday by default; invalid values raise ValueError.
    """

    start: time = time(9)
    end: time = time(17)
    weekdays: frozenset[int] = WORKDAYS

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("Working hours must end after they start")
        if not self.weekdays <= frozenset(range(7)):
            raise ValueError("weekdays must contain values from 0 (Monday) to 6 (Sunday)")

    def is_working_day(self, day: date) -> bool:
        """Return whether the day's weekday, numbered from Monday as zero, is one of the working
        days.
        """
        return day.weekday() in self.weekdays

    def window(self, day: date) -> Slot | None:
        """Return the day's working window as a half-open slot from start to end, or None when the
        day is not worked.
        """
        if not self.is_working_day(day):
            return None
        start = datetime.combine(day, self.start)
        return Slot("Working hours", start, datetime.combine(day, self.end))


def free_windows(slots: list[Slot], start: datetime, end: datetime) -> list[Slot]:
    """Return the uncovered half-open gaps between start and end in chronological order, merging
    overlapping and adjacent busy slots and ignoring time outside.
    """
    gaps: list[Slot] = []
    cursor = start
    for slot in sorted(slots, key=lambda slot: slot.start):
        if cursor >= end:
            break
        if slot.start > cursor:
            gaps.append(Slot("Free", cursor, min(slot.start, end)))
        cursor = max(cursor, slot.end)
    if cursor < end:
        gaps.append(Slot("Free", cursor, end))
    return gaps


def find_available_slot(
    agenda: Agenda,
    duration: timedelta,
    earliest: datetime,
    latest: datetime,
    hours: WorkingHours | None = None,
    title: str = "Available",
) -> Slot | None:
    """Return the earliest free slot of the duration inside working hours between earliest and
    latest inclusive, possibly touching bookings, or None; non-positive durations raise ValueError.
    """
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")
    hours = hours or WorkingHours()
    day = earliest.date()
    while day <= latest.date():
        window = hours.window(day)
        if window is not None:
            start, end = max(window.start, earliest), min(window.end, latest)
            if end > start:
                busy = agenda.slots_between(start, end)
                for gap in free_windows(busy, start, end):
                    if gap.end - gap.start >= duration:
                        return Slot(title, gap.start, gap.start + duration)
        day += timedelta(days=1)
    return None
