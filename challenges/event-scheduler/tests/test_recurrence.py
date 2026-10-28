from datetime import date

import pytest
from scheduler import add_months, daily, monthly, weekly


def test_add_months_clamps_to_month_end():
    assert add_months(date(2024, 11, 30), 3) == date(2025, 2, 28)


def test_add_months_supports_negative_offsets():
    assert add_months(date(2024, 3, 31), -1) == date(2024, 2, 29)
    assert add_months(date(2024, 1, 15), -1) == date(2023, 12, 15)


def test_daily_includes_end_date():
    assert daily(date(2024, 1, 1), date(2024, 1, 5)) == [
        date(2024, 1, 1),
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
        date(2024, 1, 5),
    ]


def test_daily_with_interval_landing_on_end_date():
    assert daily(date(2024, 1, 1), date(2024, 1, 7), interval=3) == [
        date(2024, 1, 1),
        date(2024, 1, 4),
        date(2024, 1, 7),
    ]


def test_daily_with_interval_skipping_end_date():
    assert daily(date(2024, 1, 1), date(2024, 1, 6), interval=2) == [
        date(2024, 1, 1),
        date(2024, 1, 3),
        date(2024, 1, 5),
    ]


def test_daily_with_end_before_start_is_empty():
    assert daily(date(2024, 1, 2), date(2024, 1, 1)) == []


def test_daily_rejects_invalid_interval():
    with pytest.raises(ValueError):
        daily(date(2024, 1, 1), date(2024, 1, 2), interval=0)


def test_weekly_uses_monday_as_zero():
    assert weekly(date(2024, 1, 1), date(2024, 1, 14), {0, 2}) == [
        date(2024, 1, 1),
        date(2024, 1, 3),
        date(2024, 1, 8),
        date(2024, 1, 10),
    ]


def test_weekly_rejects_invalid_weekdays():
    with pytest.raises(ValueError):
        weekly(date(2024, 1, 1), date(2024, 1, 14), {7})


def test_monthly_on_mid_month_day():
    assert monthly(date(2024, 1, 15), 3) == [
        date(2024, 1, 15),
        date(2024, 2, 15),
        date(2024, 3, 15),
    ]


def test_monthly_keeps_original_day_after_short_month():
    assert monthly(date(2024, 1, 31), 4) == [
        date(2024, 1, 31),
        date(2024, 2, 29),
        date(2024, 3, 31),
        date(2024, 4, 30),
    ]


def test_monthly_with_no_occurrences():
    assert monthly(date(2024, 1, 31), 0) == []
