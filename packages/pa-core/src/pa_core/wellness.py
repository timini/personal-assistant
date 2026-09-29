"""Wellness scales, habit cadence, and streaks.

Two behaviours here are deliberate reversals of the original design, both
because it produced a 10% habit-logging rate over five months:

1. **A period with no event does not break a streak.** Only an explicit skip
   does. Forgetting to log is not the same as not doing the thing, and treating
   them identically is what made every streak read 0 or 1.
2. **Streaks count periods, not days.** A monthly habit measured in days would
   show as permanently broken, which is the opposite of motivating.

Mood and energy are normalised to 1-5 here. Historical data holds `?`, `good`,
`okay`, `"2 - Good"` and bare digits all at once, which cannot be trended. New
captures store the normalised integer *and* the raw text, so a parser bug is
recoverable.
"""
from __future__ import annotations

import calendar
import datetime
import re
from typing import Any, Iterable

MOOD_SCALE = {
    1: "Bad — struggling",
    2: "Rough — low energy or stressed",
    3: "Okay — managing",
    4: "Good — solid",
    5: "Great — firing on all cylinders",
}
ENERGY_SCALE = MOOD_SCALE

# Words that appear in the existing logs, mapped onto the scale.
_WORDS = {
    "bad": 1, "awful": 1, "terrible": 1, "struggling": 1,
    "rough": 2, "low": 2, "tired": 2, "poor": 2,
    "okay": 3, "ok": 3, "alright": 3, "fine": 3, "managing": 3, "meh": 3,
    "good": 4, "solid": 4, "decent": 4,
    "great": 5, "excellent": 5, "amazing": 5, "brilliant": 5,
}

CADENCES = ("daily", "weekly", "monthly")

# How late in a period a non-daily habit starts being asked about. Asking on
# Monday about a weekly habit is noise that trains him to ignore the message.
_WEEKLY_ASK_FROM_WEEKDAY = 4   # Friday (Mon=0)
_MONTHLY_ASK_LAST_N_DAYS = 5


def parse_scale(raw: Any) -> int | None:
    """Normalise a free-text mood/energy answer to 1-5, or None.

    Returns None rather than guessing. A bad parse silently becoming a 3 would
    poison the very trend this exists to produce.
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None

    # A digit anywhere wins — covers "3", " 4 ", "energy 3", "2 - Good".
    match = re.search(r"\b([1-5])\b", text)
    if match:
        return int(match.group(1))

    # Reject out-of-range digits explicitly rather than falling through to the
    # word map, so "6" and "99" are None rather than accidentally matching.
    if re.search(r"\d", text):
        return None

    for word, value in _WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return None


def period_key(date_str: str, cadence: str) -> str:
    """The period a date belongs to, for the given cadence."""
    date = datetime.date.fromisoformat(date_str[:10])
    if cadence == "weekly":
        year, week, _ = date.isocalendar()
        return f"{year}-W{week:02d}"
    if cadence == "monthly":
        return f"{date.year}-{date.month:02d}"
    return date.isoformat()


def _periods_back(today: str, cadence: str, count: int) -> list[str]:
    """Period keys going backwards from today, newest first, today included."""
    date = datetime.date.fromisoformat(today[:10])
    step = {"daily": 1, "weekly": 7, "monthly": 28}[cadence]
    keys: list[str] = []
    cursor = date
    while len(keys) < count:
        key = period_key(cursor.isoformat(), cadence)
        if key not in keys:
            keys.append(key)
        cursor -= datetime.timedelta(days=step if cadence != "monthly" else 1)
        if cursor < date - datetime.timedelta(days=365 * 3):
            break
    return keys


def _by_period(
    name: str, events: Iterable[dict], cadence: str
) -> dict[str, dict[str, int]]:
    """Count completions and skips for one habit, grouped by period."""
    out: dict[str, dict[str, int]] = {}
    for event in events:
        if event.get("category") != "habit" or event.get("summary") != name:
            continue
        date_str = event.get("date")
        if not date_str:
            continue
        bucket = out.setdefault(period_key(date_str, cadence), {"completed": 0, "skipped": 0})
        action = event.get("action")
        if action in bucket:
            bucket[action] += 1
    return out


def streak(
    name: str,
    events: Iterable[dict],
    cadence: str = "daily",
    target: int = 1,
    today: str | None = None,
    lookback: int = 30,
) -> int:
    """Consecutive periods in which the habit was done at least `target` times.

    A period with no event is passed over, not counted as a break. Only an
    explicit skip breaks the run. The current, incomplete period never breaks
    it — a weekly habit not yet done on Tuesday is not a failure.
    """
    if cadence not in CADENCES:
        cadence = "daily"
    today = today or datetime.date.today().isoformat()
    counts = _by_period(name, events, cadence)
    current = period_key(today, cadence)

    run = 0
    for key in _periods_back(today, cadence, lookback):
        bucket = counts.get(key)
        if bucket is None:
            # No record. Silence is not failure — but the current period also
            # cannot yet count towards the streak.
            continue
        if bucket["completed"] >= target:
            run += 1
        elif bucket["skipped"] > 0:
            if key == current:
                continue  # skipped today does not retro-break yesterday's run
            break
    return run


def completion_rate(
    name: str,
    events: Iterable[dict],
    cadence: str = "daily",
    target: int = 1,
    today: str | None = None,
    lookback: int = 30,
) -> tuple[int, int]:
    """(periods done, periods looked at) — honest counterpart to the streak.

    A streak is fragile under sparse logging; a rate is not, and it still
    motivates. Reported against the cadence: "3 of the last 4 weeks".
    """
    if cadence not in CADENCES:
        cadence = "daily"
    today = today or datetime.date.today().isoformat()
    counts = _by_period(name, events, cadence)
    keys = _periods_back(today, cadence, lookback)
    done = sum(1 for k in keys if counts.get(k, {}).get("completed", 0) >= target)
    return done, len(keys)


def habit_due(habit: dict, events: Iterable[dict], today: str | None = None) -> bool:
    """Should the evening prompt ask about this habit tonight?

    Daily habits are asked every night unless already done. Weekly and monthly
    ones are only asked as their period runs out, because a monthly habit asked
    nightly is noise that trains him to ignore the message.
    """
    today = today or datetime.date.today().isoformat()
    cadence = habit.get("cadence", "daily")
    if cadence not in CADENCES:
        cadence = "daily"
    target = int(habit.get("target", 1) or 1)

    counts = _by_period(habit.get("name", ""), events, cadence)
    if counts.get(period_key(today, cadence), {}).get("completed", 0) >= target:
        return False  # already done this period

    date = datetime.date.fromisoformat(today[:10])
    if cadence == "daily":
        return True
    if cadence == "weekly":
        return date.weekday() >= _WEEKLY_ASK_FROM_WEEKDAY
    days_in_month = calendar.monthrange(date.year, date.month)[1]
    return date.day > days_in_month - _MONTHLY_ASK_LAST_N_DAYS


def due_habits(habits: list[dict], events: Iterable[dict], today: str | None = None) -> list[dict]:
    """The habits worth asking about tonight."""
    return [h for h in habits if habit_due(h, events, today)]
