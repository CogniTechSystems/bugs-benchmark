from datetime import date, datetime, time, timedelta

import pytest
from scheduler import (
    FRIDAY,
    MONDAY,
    SATURDAY,
    SUNDAY,
    WEDNESDAY,
    WEEKEND,
    WORKDAYS,
    Agenda,
    Event,
    RecurrenceRule,
    SchedulingConflictError,
    Slot,
    WorkingHours,
    escape_ics_text,
    find_available_slot,
    format_agenda,
    free_windows,
    parse_rule,
    parse_weekday,
    parse_weekdays,
    to_csv,
    to_ics,
    weekday_name,
)


def at(hour: int, minute: int = 0, day: int = 6) -> datetime:
    return datetime(2024, 5, day, hour, minute)


def test_weekday_constants_follow_date_weekday():
    assert date(2024, 5, 6).weekday() == MONDAY
    assert date(2024, 5, 12).weekday() == SUNDAY
    assert set(range(7)) == WORKDAYS | WEEKEND


def test_weekday_names():
    assert weekday_name(MONDAY) == "Monday"
    assert weekday_name(SATURDAY) == "Saturday"
    with pytest.raises(ValueError):
        weekday_name(7)


def test_parse_weekday_accepts_abbreviations_and_full_names():
    assert parse_weekday(" Mon ") == MONDAY
    assert parse_weekday("friday") == FRIDAY
    with pytest.raises(ValueError):
        parse_weekday("mo")


def test_parse_weekdays_supports_aliases_and_duplicates():
    assert parse_weekdays("mon, wed,Mon") == {MONDAY, WEDNESDAY}
    assert parse_weekdays("weekends,fri") == {FRIDAY, SATURDAY, SUNDAY}
    assert parse_weekdays("weekdays") == set(WORKDAYS)
    with pytest.raises(ValueError):
        parse_weekdays("mon,,tue")


def test_parse_daily_rule_with_count():
    rule = parse_rule("Daily every 3 count 3")
    assert rule == RecurrenceRule("daily", interval=3, count=3)
    assert rule.dates(date(2024, 1, 30)) == [date(2024, 1, 30), date(2024, 2, 2), date(2024, 2, 5)]


def test_daily_rule_until_stops_before_skipped_date():
    rule = parse_rule("daily every 2 until 2024-01-06")
    assert rule.dates(date(2024, 1, 1)) == [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 5)]


def test_parse_weekly_rule():
    rule = parse_rule("weekly on mon,wed count 5")
    assert rule.weekdays == {MONDAY, WEDNESDAY}
    dates = rule.dates(date(2024, 1, 1))
    assert len(dates) == 5
    assert dates == sorted(dates)
    assert dates[0] >= date(2024, 1, 1)


def test_monthly_rules():
    assert parse_rule("monthly count 3").dates(date(2024, 11, 15)) == [
        date(2024, 11, 15),
        date(2024, 12, 15),
        date(2025, 1, 15),
    ]
    assert parse_rule("monthly until 2024-03-10").dates(date(2024, 1, 15)) == [
        date(2024, 1, 15),
        date(2024, 2, 15),
    ]
    assert parse_rule("monthly until 2023-12-31").dates(date(2024, 1, 15)) == []


def test_describe_round_trips():
    for text in ("daily every 2 until 2024-02-01", "weekly on mon,fri count 4", "monthly count 2"):
        assert parse_rule(text).describe() == text


@pytest.mark.parametrize(
    "text",
    [
        "",
        "yearly count 2",
        "daily",
        "daily count 2 until 2024-01-01",
        "daily count",
        "daily count 0",
        "daily count -1",
        "daily count 2 count 3",
        "daily count 2 every 1x",
        "daily count 2 at noon",
        "weekly count 2",
        "monthly on mon count 2",
        "monthly every 2 count 2",
        "daily until 2024-13-01",
    ],
)
def test_parse_rule_rejects_invalid_rules(text: str):
    with pytest.raises(ValueError):
        parse_rule(text)


def test_slot_contains_start_but_not_end():
    slot = Slot("Review", at(9), at(10))
    assert slot.contains(at(9))
    assert slot.contains(at(9, 59))
    assert not slot.contains(at(10))
    assert not slot.contains(at(8, 59))


def test_slot_shifted():
    moved = Slot("Review", at(9), at(10)).shifted(timedelta(days=1))
    assert moved == Slot("Review", at(9, day=7), at(10, day=7))


def test_event_requires_positive_duration():
    with pytest.raises(ValueError):
        Event("Empty", at(9), timedelta(0))


def test_single_event_has_one_occurrence():
    event = Event("Review", at(9), timedelta(minutes=45))
    assert event.occurrences() == [Slot("Review", at(9), at(9, 45))]


def test_recurring_event_occurrences_keep_time_of_day():
    event = Event("Standup", at(9, 30), timedelta(minutes=15), parse_rule("daily count 3"))
    assert [slot.start for slot in event.occurrences()] == [
        at(9, 30, day=6),
        at(9, 30, day=7),
        at(9, 30, day=8),
    ]


def build_agenda() -> Agenda:
    agenda = Agenda()
    agenda.add(Event("Standup", at(9), timedelta(minutes=30), parse_rule("daily count 5")))
    agenda.add(Event("Planning", at(13), timedelta(hours=1)))
    return agenda


def test_agenda_lists_events_and_slots_in_order():
    agenda = build_agenda()
    assert [event.title for event in agenda.events] == ["Standup", "Planning"]
    slots = agenda.slots()
    assert len(slots) == 6
    assert [slot.title for slot in slots[:3]] == ["Standup", "Planning", "Standup"]


def test_agenda_rejects_duplicate_titles():
    agenda = build_agenda()
    with pytest.raises(ValueError):
        agenda.add(Event("Planning", at(15), timedelta(hours=1)))


def test_agenda_rejects_overlapping_events():
    agenda = build_agenda()
    with pytest.raises(SchedulingConflictError) as raised:
        agenda.add(Event("Call", at(9, 15, day=8), timedelta(minutes=30)))
    assert (raised.value.event, raised.value.existing) == ("Call", "Standup")
    assert "Call" not in [event.title for event in agenda.events]


def test_agenda_can_accept_conflicts_explicitly():
    agenda = build_agenda()
    agenda.add(Event("Call", at(13, 30), timedelta(minutes=30)), allow_conflicts=True)
    assert agenda.conflicts() == [("Planning", "Call")]


def test_agenda_remove():
    agenda = build_agenda()
    assert agenda.remove("Planning").title == "Planning"
    assert agenda.conflicts() == []
    with pytest.raises(KeyError):
        agenda.remove("Planning")


def test_slots_between_and_on_day():
    agenda = build_agenda()
    assert [slot.title for slot in agenda.slots_between(at(8), at(12))] == ["Standup"]
    assert [slot.start for slot in agenda.slots_between(at(9, 15), at(9, 20))] == [at(9)]
    assert [slot.title for slot in agenda.slots_on(date(2024, 5, 6))] == ["Standup", "Planning"]
    assert agenda.slots_on(date(2024, 5, 11)) == []


def test_working_hours_window():
    hours = WorkingHours()
    assert hours.window(date(2024, 5, 6)) == Slot("Working hours", at(9), at(17))
    assert hours.window(date(2024, 5, 11)) is None
    assert WorkingHours(weekdays=frozenset({SATURDAY})).is_working_day(date(2024, 5, 11))


def test_working_hours_validation():
    with pytest.raises(ValueError):
        WorkingHours(start=time(17), end=time(9))
    with pytest.raises(ValueError):
        WorkingHours(weekdays=frozenset({7}))


def test_free_windows_between_busy_slots():
    busy = [
        Slot("Lunch", at(12), at(13)),
        Slot("Standup", at(9), at(9, 30)),
        Slot("Review", at(9, 15), at(10)),
        Slot("Late", at(16, 30), at(18)),
    ]
    assert free_windows(busy, at(9), at(17)) == [
        Slot("Free", at(10), at(12)),
        Slot("Free", at(13), at(16, 30)),
    ]


def test_free_windows_merges_adjacent_slots():
    busy = [Slot("First", at(10), at(11)), Slot("Second", at(11), at(12))]
    assert free_windows(busy, at(9), at(13)) == [
        Slot("Free", at(9), at(10)),
        Slot("Free", at(12), at(13)),
    ]


def test_free_windows_with_no_busy_time():
    assert free_windows([], at(9), at(10)) == [Slot("Free", at(9), at(10))]
    assert free_windows([Slot("All day", at(8), at(18))], at(9), at(17)) == []


def test_find_available_slot_starts_when_meeting_ends():
    agenda = build_agenda()
    found = find_available_slot(agenda, timedelta(hours=1), at(9), at(17))
    assert found == Slot("Available", at(9, 30), at(10, 30))


def test_find_available_slot_respects_earliest_and_length():
    agenda = build_agenda()
    found = find_available_slot(agenda, timedelta(hours=3), at(11), at(17, day=7), title="Workshop")
    assert found == Slot("Workshop", at(14), at(17))


def test_find_available_slot_skips_days_off():
    agenda = build_agenda()
    found = find_available_slot(agenda, timedelta(hours=1), at(17, day=10), at(17, day=14))
    assert found == Slot("Available", at(9, day=13), at(10, day=13))


def test_find_available_slot_returns_none_without_room():
    agenda = build_agenda()
    assert find_available_slot(agenda, timedelta(hours=9), at(0), at(23, day=10)) is None
    with pytest.raises(ValueError):
        find_available_slot(agenda, timedelta(0), at(9), at(17))


def test_escape_ics_text():
    assert escape_ics_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


def test_to_ics():
    slots = [Slot("Review, final", at(14), at(15)), Slot("Standup", at(9), at(9, 15))]
    document = to_ics(slots, "Team", datetime(2024, 5, 1, 8))
    lines = document.split("\r\n")
    assert lines[:4] == [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//scheduler//EN",
        "X-WR-CALNAME:Team",
    ]
    assert lines[4:11] == [
        "BEGIN:VEVENT",
        "UID:0-20240506T090000@scheduler",
        "DTSTAMP:20240501T080000",
        "DTSTART:20240506T090000",
        "DTEND:20240506T091500",
        "SUMMARY:Standup",
        "END:VEVENT",
    ]
    assert "SUMMARY:Review\\, final" in lines
    assert document.endswith("END:VCALENDAR\r\n")


def test_to_csv():
    slots = [Slot("Lunch, team", at(12), at(13)), Slot("Standup", at(9), at(9, 15))]
    assert to_csv(slots).splitlines() == [
        "title,start,end,duration_minutes",
        "Standup,2024-05-06T09:00:00,2024-05-06T09:15:00,15",
        '"Lunch, team",2024-05-06T12:00:00,2024-05-06T13:00:00,60',
    ]


def test_format_agenda_groups_by_day():
    slots = [
        Slot("Planning", at(13), at(14)),
        Slot("Standup", at(9), at(9, 15)),
        Slot("Retro", at(16, day=7), at(17, day=7)),
    ]
    assert format_agenda(slots) == "\n".join(
        [
            "Monday 2024-05-06",
            "  09:00-09:15 Standup",
            "  13:00-14:00 Planning",
            "Tuesday 2024-05-07",
            "  16:00-17:00 Retro",
        ]
    )
    assert format_agenda([]) == ""
