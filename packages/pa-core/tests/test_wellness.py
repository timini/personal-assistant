"""Wellness scales, habit cadence and streaks.

Two behaviours here are deliberate reversals of what the code used to do, and
both exist because the old behaviour produced a 10% habit-logging rate:

1. A day with no event does NOT break a streak. Only an explicit skip does.
   Forgetting to log is not the same as not doing the thing.
2. Streaks count *periods*, not days. A monthly habit measured in days would
   read as permanently broken.
"""
import pytest

from pa_core.wellness import (
    habit_due,
    parse_scale,
    period_key,
    streak,
)


# --- scales -----------------------------------------------------------------
# These are the actual values found in activity/daily/*.json. If parse_scale
# cannot handle them, the mood trend is worthless.

@pytest.mark.parametrize("raw,expected", [
    ("1", 1), ("3", 3), ("5", 5),
    ("2 - Good", 2),          # hybrid form already in the data
    ("good", 4),
    ("okay", 3), ("ok", 3),
    ("rough", 2),
    ("bad", 1),
    ("great", 5),
    ("  4  ", 4),
    ("energy 3", 3),
    ("meh-ish", 3),          # hyphen is a word boundary; a legitimate match, not a guess
])
def test_parse_scale_handles_the_real_historical_values(raw, expected):
    assert parse_scale(raw) == expected


@pytest.mark.parametrize("raw", ["?", "", None, "dunno", "no idea", "99"])
def test_parse_scale_returns_none_rather_than_guessing(raw):
    """A bad parse must never silently become a 3 — that would poison the trend."""
    assert parse_scale(raw) is None


def test_parse_scale_clamps_out_of_range_digits():
    assert parse_scale("0") is None
    assert parse_scale("6") is None


# --- periods ----------------------------------------------------------------

def test_daily_period_is_the_date():
    assert period_key("2026-08-24", "daily") == "2026-08-24"


def test_weekly_period_groups_a_monday_to_sunday_week():
    # 2026-08-24 is a Monday; 2026-08-30 the Sunday of the same ISO week
    assert period_key("2026-08-24", "weekly") == period_key("2026-08-30", "weekly")
    assert period_key("2026-08-23", "weekly") != period_key("2026-08-24", "weekly")


def test_monthly_period_groups_a_calendar_month():
    assert period_key("2026-08-01", "monthly") == period_key("2026-08-31", "monthly")
    assert period_key("2026-08-31", "monthly") != period_key("2026-09-01", "monthly")


# --- streaks ----------------------------------------------------------------

def _ev(date, name, action):
    return {"date": date, "category": "habit", "action": action, "summary": name}


def test_a_gap_does_not_break_a_streak():
    """The behaviour change. Silence is not failure."""
    events = [
        _ev("2026-08-20", "Exercise", "completed"),
        # 21st: nothing logged at all
        _ev("2026-08-22", "Exercise", "completed"),
        _ev("2026-08-23", "Exercise", "completed"),
    ]
    assert streak("Exercise", events, "daily", today="2026-08-24") == 3


def test_an_explicit_skip_breaks_a_streak():
    events = [
        _ev("2026-08-20", "Exercise", "completed"),
        _ev("2026-08-21", "Exercise", "skipped"),
        _ev("2026-08-22", "Exercise", "completed"),
        _ev("2026-08-23", "Exercise", "completed"),
    ]
    assert streak("Exercise", events, "daily", today="2026-08-24") == 2


def test_weekly_streak_counts_weeks_not_days():
    """One completion a week is a perfect weekly streak, not a broken daily one."""
    events = [
        _ev("2026-08-10", "Deep clean", "completed"),
        _ev("2026-08-18", "Deep clean", "completed"),
        _ev("2026-08-24", "Deep clean", "completed"),
    ]
    assert streak("Deep clean", events, "weekly", today="2026-08-26") == 3


def test_monthly_streak_counts_months():
    events = [
        _ev("2026-06-14", "Review finances", "completed"),
        _ev("2026-07-02", "Review finances", "completed"),
        _ev("2026-08-19", "Review finances", "completed"),
    ]
    assert streak("Review finances", events, "monthly", today="2026-08-24") == 3


def test_the_current_incomplete_period_never_breaks_a_streak():
    """A weekly habit not yet done on Tuesday is not a failure."""
    events = [
        _ev("2026-08-10", "Deep clean", "completed"),
        _ev("2026-08-18", "Deep clean", "completed"),
    ]
    # today is Tue 25 Aug, this week's not done yet — streak should still read 2
    assert streak("Deep clean", events, "weekly", today="2026-08-25") == 2


def test_target_requires_multiple_completions_in_a_period():
    events = [
        _ev("2026-08-18", "Exercise", "completed"),
        _ev("2026-08-19", "Exercise", "completed"),
        _ev("2026-08-20", "Exercise", "completed"),
    ]
    assert streak("Exercise", events, "weekly", target=3, today="2026-08-24") == 1
    assert streak("Exercise", events, "weekly", target=4, today="2026-08-24") == 0


def test_other_habits_do_not_pollute_a_streak():
    events = [
        _ev("2026-08-22", "Exercise", "completed"),
        _ev("2026-08-23", "Reading", "skipped"),
        _ev("2026-08-23", "Exercise", "completed"),
    ]
    assert streak("Exercise", events, "daily", today="2026-08-24") == 2


def test_no_events_is_a_zero_streak_not_an_error():
    assert streak("Exercise", [], "daily", today="2026-08-24") == 0


# --- which habits to ask about ---------------------------------------------

def test_daily_habits_are_always_due():
    h = {"name": "Exercise", "cadence": "daily"}
    assert habit_due(h, [], today="2026-08-24") is True


def test_a_daily_habit_already_done_today_is_not_asked_again():
    h = {"name": "Exercise", "cadence": "daily"}
    events = [_ev("2026-08-24", "Exercise", "completed")]
    assert habit_due(h, events, today="2026-08-24") is False


def test_a_weekly_habit_is_not_asked_early_in_the_week():
    """Asking on Monday about a weekly habit is noise that trains him to ignore it."""
    h = {"name": "Deep clean", "cadence": "weekly"}
    assert habit_due(h, [], today="2026-08-24") is False   # Monday


def test_a_weekly_habit_is_asked_as_the_week_runs_out():
    h = {"name": "Deep clean", "cadence": "weekly"}
    assert habit_due(h, [], today="2026-08-29") is True    # Saturday


def test_a_weekly_habit_already_done_is_not_asked_at_all():
    h = {"name": "Deep clean", "cadence": "weekly"}
    events = [_ev("2026-08-24", "Deep clean", "completed")]
    assert habit_due(h, events, today="2026-08-29") is False


def test_a_monthly_habit_is_only_asked_near_month_end():
    h = {"name": "Review finances", "cadence": "monthly"}
    assert habit_due(h, [], today="2026-08-10") is False
    assert habit_due(h, [], today="2026-08-28") is True
