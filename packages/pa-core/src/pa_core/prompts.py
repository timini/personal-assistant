"""Build the morning planning prompt and the evening reflection prompt.

Pure text assembly — no network, no model, no side effects, so it is cheap to
test and cheap to run on a schedule. `scripts/wellness_prompt.py` fetches the
inputs and sends the result.

The morning prompt is the important one. Measured across 104 days, days that
start with a plan complete 3.26 tasks against 1.27, and the median moves from
0 to 2. Planning was happening on 35% of days because nothing prompted it. So
this prompt arrives already carrying the day — schedule, shortlist, questions —
and replying to it *is* planning. That is the whole design.
"""
from __future__ import annotations

import datetime

from pa_core.wellness import due_habits

MAX_SHORTLIST = 5

# Overdue by more than this is a stale date, not urgent work. Leading with
# months-old items reads as an accusation and is what people avoid opening.
STALE_AFTER_DAYS = 30

# Lane names as stored in Notion.
_LANE_LIVE = "🔥 Live"
_LANE_PARKED = "🅿️ Parked"
_LANE_SOMEDAY = "💤 Someday"


def shortlist(tasks: list[dict], today: str | None = None) -> list[dict]:
    """Up to five tasks worth doing today, most pressing first.

    Deliberately deterministic. A model-curated list matched to energy would be
    better, but it cannot run before the reply arrives, and a prompt that goes
    out on time beats a cleverer one that does not.
    """
    today = today or datetime.date.today().isoformat()
    today_date = datetime.date.fromisoformat(today[:10])
    live: list[dict] = []
    overdue: list[dict] = []
    soon: list[dict] = []
    rest: list[dict] = []
    stale: list[dict] = []

    for task in tasks:
        if task.get("lane") in (_LANE_PARKED, _LANE_SOMEDAY):
            continue
        due = task.get("due_date") or ""
        if task.get("lane") == _LANE_LIVE:
            live.append(task)
        elif due and due < today:
            age = (today_date - datetime.date.fromisoformat(due[:10])).days
            (stale if age > STALE_AFTER_DAYS else overdue).append(task)
        elif due:
            soon.append(task)
        else:
            rest.append(task)

    overdue.sort(key=lambda t: t.get("due_date", ""), reverse=True)  # most recent first
    soon.sort(key=lambda t: t.get("due_date", ""))
    stale.sort(key=lambda t: t.get("due_date", ""), reverse=True)
    return (live + overdue + soon + rest + stale)[:MAX_SHORTLIST]


def build_morning_prompt(
    schedule: list[dict],
    tasks: list[dict],
    today: str | None = None,
    health: dict | None = None,
) -> str:
    """The 06:30 message: the day, a shortlist, and three questions."""
    today = today or datetime.date.today().isoformat()
    day_name = datetime.date.fromisoformat(today[:10]).strftime("%A")

    lines = [f"☀️ Morning. It's {day_name}.", ""]

    if health and health.get("ok"):
        bits = []
        if health.get("sleep_hours"):
            bits.append(f"{health['sleep_hours']}h sleep")
        if health.get("body_battery_high"):
            bits.append(f"body battery {health['body_battery_high']}")
        if bits:
            lines += [" · ".join(bits), ""]

    if schedule:
        lines.append("TODAY")
        for event in schedule:
            time = event.get("time") or ""
            # All-day events carry the date in `time`; showing it raw is noise.
            if not time or len(time) > 5:
                time = "all-day"
            cal = f" [{event['calendar']}]" if event.get("calendar") else ""
            lines.append(f"  {time}  {event.get('summary', '')}{cal}")
    else:
        lines.append("TODAY — calendar is clear.")
    lines.append("")

    picks = shortlist(tasks, today)
    if picks:
        lines.append("WORTH DOING")
        for i, task in enumerate(picks, 1):
            due = task.get("due_date") or ""
            flag = ""
            if due and due < today:
                flag = f"  (overdue {due})"
            elif due:
                flag = f"  (due {due})"
            lines.append(f"  {i}. {task.get('title', '')}{flag}")
    else:
        lines.append("WORTH DOING — nothing pressing on the list.")
    lines += ["", "———", ""]

    lines += [
        "Reply with:",
        "  • Mood 1-5",
        "  • Energy 1-5",
        "  • One thing you're doing to get going",
        "  • Which numbers above you're taking on (or none)",
        "",
        "Whatever you pick, I'll put on your phone with today's date.",
    ]
    return "\n".join(lines)


def build_evening_prompt(
    habits: list[dict],
    events: list[dict],
    today: str | None = None,
    tomorrow_tasks: list[dict] | None = None,
) -> str:
    """The 21:00 message: reflect, log, wind down, look at tomorrow.

    Only asks about habits actually due — a monthly habit asked every night is
    noise that trains him to ignore the message.
    """
    today = today or datetime.date.today().isoformat()
    lines = ["🌙 Evening.", ""]

    due = due_habits(habits, events, today)
    if due:
        lines.append("HABITS — done any of these?")
        for habit in due:
            emoji = habit.get("emoji", "•")
            cadence = habit.get("cadence", "daily")
            note = "" if cadence == "daily" else f"  ({cadence})"
            lines.append(f"  {emoji} {habit.get('name', '')}{note}")
        lines.append("")

    lines += [
        "One thing you're grateful for today?",
        "",
        "And how did the day actually go?",
        "",
    ]

    if tomorrow_tasks:
        lines.append("TOMORROW")
        for task in tomorrow_tasks[:3]:
            lines.append(f"  • {task.get('title', '')}")
        lines.append("")

    lines += [
        "———",
        "Then switch off. Screens down, get some proper rest so tomorrow starts well.",
    ]
    return "\n".join(lines)
