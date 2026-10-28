"""Events and the agenda that stores them and expands them into concrete occurrences."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from scheduler.rules import RecurrenceRule
from scheduler.slots import Slot, find_conflicts


class SchedulingConflictError(Exception):
    """Raised when an event would overlap an event already on the agenda."""

    def __init__(self, event: str, existing: str) -> None:
        """Record the titles of the new event and of the existing event it collides with."""
        super().__init__(f"{event!r} overlaps {existing!r}")
        self.event = event
        self.existing = existing


@dataclass(frozen=True)
class Event:
    """A titled event lasting a positive duration from its start, repeated by an optional rule,
    raising ValueError on creation for a non-positive duration.
    """

    title: str
    start: datetime
    duration: timedelta
    rule: RecurrenceRule | None = None

    def __post_init__(self) -> None:
        if self.duration <= timedelta(0):
            raise ValueError("An event must have a positive duration")

    def occurrences(self) -> list[Slot]:
        """Return a slot for each occurrence date, starting at the event's time of day and lasting
        its duration, in chronological order.
        """
        days = self.rule.dates(self.start.date()) if self.rule else [self.start.date()]
        clock = self.start.timetz()
        starts = (datetime.combine(day, clock) for day in days)
        return [Slot(self.title, start, start + self.duration) for start in starts]


class Agenda:
    """A collection of events, each identified by a unique title."""

    def __init__(self) -> None:
        """Create an empty agenda."""
        self._events: dict[str, Event] = {}

    @property
    def events(self) -> list[Event]:
        """Return the events on the agenda ordered by their first start time."""
        return sorted(self._events.values(), key=lambda event: event.start)

    def add(self, event: Event, *, allow_conflicts: bool = False) -> None:
        """Store the event, raising ValueError for a duplicate title or, unless conflicts are
        allowed, a conflict error when an occurrence shares any instant with existing ones.
        """
        if event.title in self._events:
            raise ValueError(f"An event titled {event.title!r} already exists")
        if not allow_conflicts:
            existing = self.slots()
            for slot in event.occurrences():
                clash = next((other for other in existing if slot.overlaps(other)), None)
                if clash is not None:
                    raise SchedulingConflictError(event.title, clash.title)
        self._events[event.title] = event

    def remove(self, title: str) -> Event:
        """Remove and return the event with the given title, raising KeyError when no such event
        exists.
        """
        return self._events.pop(title)

    def slots(self) -> list[Slot]:
        """Return every occurrence of every event on the agenda, ordered by start time and then by
        title.
        """
        occurrences = [slot for event in self._events.values() for slot in event.occurrences()]
        return sorted(occurrences, key=lambda slot: (slot.start, slot.title))

    def slots_between(self, start: datetime, end: datetime) -> list[Slot]:
        """Return whole occurrences sharing any instant with the half-open window from start up to
        but excluding end, ordered by start then title.
        """
        window = Slot("Window", start, end)
        return [slot for slot in self.slots() if slot.overlaps(window)]

    def slots_on(self, day: date) -> list[Slot]:
        """Return whole occurrences sharing any instant with the given day, from its midnight up to
        but excluding the next midnight.
        """
        midnight = datetime.combine(day, time())
        return self.slots_between(midnight, midnight + timedelta(days=1))

    def conflicts(self) -> list[tuple[str, str]]:
        """Return the title pairs of every two occurrences on the agenda that share any instant,
        earlier starting occurrence first.
        """
        return find_conflicts(self.slots())
