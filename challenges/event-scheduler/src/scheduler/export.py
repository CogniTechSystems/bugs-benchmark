"""Export of slots to iCalendar, CSV and plain text agendas."""

import csv
import io
from datetime import date, datetime

from scheduler.slots import Slot
from scheduler.weekdays import weekday_name

ICS_TIMESTAMP = "%Y%m%dT%H%M%S"


def escape_ics_text(text: str) -> str:
    """Return text escaped for an iCalendar value, prefixing backslashes, semicolons and commas with
    a backslash and writing each line break as an escaped newline.
    """
    escaped = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return escaped.replace("\r\n", "\\n").replace("\n", "\\n")


def to_ics(slots: list[Slot], name: str, stamp: datetime) -> str:
    """Return the slots sorted by start as a named iCalendar document with CRLF line endings,
    floating local times, the given stamp and exclusive end times.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//scheduler//EN",
        f"X-WR-CALNAME:{escape_ics_text(name)}",
    ]
    for index, slot in enumerate(sorted(slots, key=lambda slot: slot.start)):
        lines += [
            "BEGIN:VEVENT",
            f"UID:{index}-{slot.start.strftime(ICS_TIMESTAMP)}@scheduler",
            f"DTSTAMP:{stamp.strftime(ICS_TIMESTAMP)}",
            f"DTSTART:{slot.start.strftime(ICS_TIMESTAMP)}",
            f"DTEND:{slot.end.strftime(ICS_TIMESTAMP)}",
            f"SUMMARY:{escape_ics_text(slot.title)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def to_csv(slots: list[Slot]) -> str:
    """Return the slots sorted by start as CSV with a header row and title, ISO start, ISO end and
    whole duration minutes columns.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["title", "start", "end", "duration_minutes"])
    for slot in sorted(slots, key=lambda slot: slot.start):
        writer.writerow(
            [slot.title, slot.start.isoformat(), slot.end.isoformat(), slot.duration_minutes]
        )
    return buffer.getvalue()


def format_agenda(slots: list[Slot]) -> str:
    """Return one line per slot sorted by start, under a heading of weekday name and ISO date for
    each day, or an empty string for none.
    """
    lines: list[str] = []
    current_day: date | None = None
    for slot in sorted(slots, key=lambda slot: slot.start):
        day = slot.start.date()
        if day != current_day:
            lines.append(f"{weekday_name(day.weekday())} {day.isoformat()}")
            current_day = day
        lines.append(f"  {slot.start:%H:%M}-{slot.end:%H:%M} {slot.title}")
    return "\n".join(lines)
