"""Build the morning planning prompt and the evening reflection prompt.

Pure text assembly: no network, no model, no side effects, so it is cheap to
test. `pa-core checkin` fetches the inputs and prints the result; the agent
harness decides when to run it.

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
    """The morning message: the day, a shortlist, and three questions."""
    today = today or datetime.date.today().isoformat()
    day_name = datetime.date.fromisoformat(today[:10]).strftime("%A")

    lines = [f"☀️ Morning. It's {day_name}.", ""]

    if health and health.get("ok"):
        bits = []
        if health.get("sleep_hours"):
            bits.append(f"{health['sleep_hours']}h sleep")
        if health.get("body_battery_high"):
            bits.append(f"body battery {health['body_battery_high']}")
        for activity in health.get("activities") or []:
            label = activity.get("type") or "session"
            measure = (
                f"{activity['distance_km']} km" if activity.get("distance_km")
                else f"{activity['duration_min']} min" if activity.get("duration_min")
                else None
            )
            if measure:
                pr = " 🏅 PR" if activity.get("is_pr") else ""
                bits.append(f"{label} {measure}{pr}")
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
        "Whatever you pick, I'll set it due today in Notion.",
    ]
    return "\n".join(lines)


def build_evening_prompt(
    habits: list[dict],
    events: list[dict],
    today: str | None = None,
    tomorrow_tasks: list[dict] | None = None,
) -> str:
    """The evening message: reflect, log, wind down, look at tomorrow.

    Only asks about habits actually due — a monthly habit asked every night is
    noise that trains the user to ignore the message.
    """
    today = today or datetime.date.today().isoformat()
    lines = ["🌙 Evening.", ""]

    # Daily log files carry the date at file level, so their event dicts do
    # not. Attach today's date before cadence grouping. Gratitude and day
    # planning already have dedicated questions and should not be duplicated
    # in the generic habit checklist.
    dated_events = [{**event, "date": event.get("date", today)} for event in events]
    dedicated = {"gratitude", "day planning"}
    due = [
        habit for habit in due_habits(habits, dated_events, today)
        if habit.get("name", "").strip().lower() not in dedicated
    ]
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
