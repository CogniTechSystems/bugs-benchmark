from datetime import datetime

import pytest
from scheduler import Slot, find_conflicts, free_minutes


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 5, 6, hour, minute)


def test_slot_must_end_after_start():
    with pytest.raises(ValueError):
        Slot("Invalid", at(10), at(10))


def test_duration_minutes():
    assert Slot("Review", at(9), at(10, 30)).duration_minutes == 90


def test_overlapping_slots_conflict():
    slots = [Slot("Standup", at(9), at(10, 30)), Slot("Review", at(10), at(11))]
    assert find_conflicts(slots) == [("Standup", "Review")]


def test_nested_slot_conflicts():
    slots = [Slot("Workshop", at(9), at(12)), Slot("Call", at(10), at(10, 30))]
    assert find_conflicts(slots) == [("Workshop", "Call")]


def test_back_to_back_slots_do_not_conflict():
    first = Slot("Standup", at(9), at(10))
    second = Slot("Review", at(10), at(11))
    assert not first.overlaps(second)
    assert find_conflicts([second, first]) == []


def test_free_minutes_merges_overlapping_slots():
    slots = [
        Slot("Standup", at(9), at(10, 30)),
        Slot("Review", at(10), at(11)),
        Slot("Lunch", at(12), at(13)),
    ]
    assert free_minutes(slots, at(9), at(17)) == 300


def test_free_minutes_ignores_time_outside_the_day():
    slots = [Slot("Late", at(16), at(19))]
    assert free_minutes(slots, at(9), at(17)) == 420
