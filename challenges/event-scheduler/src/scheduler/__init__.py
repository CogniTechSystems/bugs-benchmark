"""Calendars of recurring events with conflict detection, free time search and export."""

from scheduler.agenda import Agenda, Event, SchedulingConflictError
from scheduler.availability import WorkingHours, find_available_slot, free_windows
from scheduler.export import escape_ics_text, format_agenda, to_csv, to_ics
from scheduler.recurrence import add_months, daily, monthly, weekly
from scheduler.rules import RecurrenceRule, parse_rule
from scheduler.slots import Slot, find_conflicts, free_minutes
from scheduler.weekdays import (
    FRIDAY,
    MONDAY,
    SATURDAY,
    SUNDAY,
    THURSDAY,
    TUESDAY,
    WEDNESDAY,
    WEEKEND,
    WORKDAYS,
    parse_weekday,
    parse_weekdays,
    weekday_name,
)

__all__ = [
    "FRIDAY",
    "MONDAY",
    "SATURDAY",
    "SUNDAY",
    "THURSDAY",
    "TUESDAY",
    "WEDNESDAY",
    "WEEKEND",
    "WORKDAYS",
    "Agenda",
    "Event",
    "RecurrenceRule",
    "SchedulingConflictError",
    "Slot",
    "WorkingHours",
    "add_months",
    "daily",
    "escape_ics_text",
    "find_available_slot",
    "find_conflicts",
    "format_agenda",
    "free_minutes",
    "free_windows",
    "monthly",
    "parse_rule",
    "parse_weekday",
    "parse_weekdays",
    "to_csv",
    "to_ics",
    "weekday_name",
    "weekly",
]
