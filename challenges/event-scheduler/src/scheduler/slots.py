"""Meeting slots, conflict detection and free time calculation."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from itertools import combinations


@dataclass(frozen=True)
class Slot:
    """A titled half-open interval from start up to but excluding end, raising ValueError on
    creation unless end is strictly after start.
    """

    title: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("A slot must end after it starts")

    @property
    def duration_minutes(self) -> int:
        """Return the length of the slot in whole minutes, rounded down."""
        return int((self.end - self.start).total_seconds() // 60)

    def contains(self, moment: datetime) -> bool:
        """Return whether the moment lies in the slot, including the start instant but excluding the
        end instant.
        """
        return self.start <= moment < self.end

    def shifted(self, delta: timedelta) -> "Slot":
        """Return a copy of the slot moved by the delta, keeping its title and length."""
        return replace(self, start=self.start + delta, end=self.end + delta)

    def overlaps(self, other: "Slot") -> bool:
        """Return whether the two half-open slots share any instant, so slots that only touch at a
        boundary do not intersect.
        """
        return self.start <= other.end and other.start <= self.end


def find_conflicts(slots: list[Slot]) -> list[tuple[str, str]]:
    """Return title pairs of every two slots sharing any instant, each pair once with the earlier
    starting slot first, touching slots excluded.
    """
    ordered = sorted(slots, key=lambda slot: slot.start)
    return [
        (first.title, second.title)
        for first, second in combinations(ordered, 2)
        if first.overlaps(second)
    ]


def free_minutes(slots: list[Slot], day_start: datetime, day_end: datetime) -> int:
    """Return whole minutes between day start and day end not covered by any slot, counting
    overlapping coverage once and ignoring time outside the day.
    """
    busy_seconds = 0.0
    cursor = day_start
    for slot in sorted(slots, key=lambda slot: slot.start):
        start = max(slot.start, cursor)
        end = min(slot.end, day_end)
        if end > start:
            busy_seconds += (end - start).total_seconds()
            cursor = end
    total_seconds = (day_end - day_start).total_seconds()
    return int((total_seconds - busy_seconds) // 60)
