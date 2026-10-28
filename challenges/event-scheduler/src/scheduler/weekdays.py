"""Weekday constants and parsing of English weekday names."""

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

WORKDAYS = frozenset({MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY})
WEEKEND = frozenset({SATURDAY, SUNDAY})

_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_ALIASES = {"weekdays": WORKDAYS, "weekends": WEEKEND}


def weekday_name(day: int) -> str:
    """Return the English name of a weekday number counted from Monday as zero, raising ValueError
    outside zero to six.
    """
    if day not in range(7):
        raise ValueError(f"Invalid weekday number: {day}")
    return _NAMES[day]


def parse_weekday(name: str) -> int:
    """Return the weekday number, from Monday as zero, for a full or three-letter name, ignoring
    case and surrounding whitespace; raises ValueError otherwise.
    """
    cleaned = name.strip().lower()
    for number, full_name in enumerate(_NAMES):
        if cleaned in (full_name.lower(), full_name[:3].lower()):
            return number
    raise ValueError(f"Unknown weekday: {name!r}")


def parse_weekdays(text: str) -> set[int]:
    """Return the weekday numbers, from Monday as zero, named in a comma separated list, accepting
    weekday and weekend aliases; empty items raise ValueError.
    """
    days: set[int] = set()
    for item in text.split(","):
        cleaned = item.strip().lower()
        if not cleaned:
            raise ValueError(f"Empty weekday in {text!r}")
        days |= _ALIASES.get(cleaned) or {parse_weekday(cleaned)}
    return days
