"""Generate daily briefing from event log, calendar, and tasks."""

from datetime import date, datetime, timedelta
from pathlib import Path

from pa_core.config import PA_ROOT, get_assistant_name, get_user_config
from pa_core.daily_log import get_events, _today_str

BRIEFINGS_DIR = PA_ROOT / "activity" / "briefings"

PRIORITY_ORDER = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3, "": 4}


def _task_sort_key(task: dict) -> tuple:
    """Sort: overdue first, then by priority, then by due date proximity."""
    today = date.today().isoformat()
    due = task.get("due_date", "")
    is_overdue = due and due < today
    priority_rank = PRIORITY_ORDER.get(task.get("priority", ""), 4)
    due_sort = due if due else "9999-99-99"
    return (not is_overdue, priority_rank, due_sort)


def _wellness_section(events: list[dict]) -> list[str]:
    """Build 'How You're Doing' section from wellness check-ins."""
    checkins = [e for e in events if e["category"] == "wellness" and e["action"] == "check_in"]
    if not checkins:
        return ["## How You're Doing\n", "_No check-in yet today._", ""]

    latest = checkins[-1]
    details = latest.get("details", {})
    mood = details.get("mood", "unknown")
    energy = details.get("energy", "unknown")
    parts = [f"Mood: {mood} | Energy: {energy}"]
    if details.get("physical"):
        parts.append(f"Physical: {details['physical']}")
    if details.get("note"):
        parts.append(f'"{details["note"]}"')

    lines = ["## How You're Doing\n"]
    lines.append(f"- {' | '.join(parts)}")
    lines.append("")
    return lines


def _health_section(health: dict | None) -> list[str]:
    """Build a compact health section, omitting metrics that are missing."""
    lines = ["## Health\n"]
    if not health or not health.get("ok"):
        return lines + ["_Health data unavailable._", ""]

    if health.get("sleep_hours") is not None:
        quality = health.get("sleep_quality")
        suffix = f" ({quality})" if quality else ""
        lines.append(f"- Sleep: {health['sleep_hours']}h{suffix}")
    if health.get("resting_hr") is not None:
        lines.append(f"- Resting heart rate: {health['resting_hr']} bpm")
    if health.get("hrv") is not None:
        lines.append(f"- HRV (7-day average): {health['hrv']} ms")
    if health.get("avg_stress") is not None:
        maximum = health.get("max_stress")
        suffix = f", {maximum} max" if maximum is not None else ""
        lines.append(f"- Stress: {health['avg_stress']} average{suffix}")
    low = health.get("body_battery_low")
    high = health.get("body_battery_high")
    if low is not None or high is not None:
        lines.append(f"- Body Battery: {low if low is not None else '?'}-{high if high is not None else '?'}")
    if health.get("steps") is not None:
        lines.append(f"- Steps: {health['steps']:,}")
    lines += _activity_lines(health.get("activities") or [])
    week = _running_week_line(health.get("running_week") or {})
    if week:
        lines.append(week)
    lines += _alert_lines(health.get("abnormal_hr") or [])
    lines.append("")
    return lines


def _running_week_line(summary: dict) -> str:
    """One line of running volume for the last 7 days.

    For someone building running volume, the weekly total is more useful than
    today's run. Average heart rate rides along so the easy/hard split is
    visible without going looking.
    """
    if not summary or not summary.get("runs"):
        return ""
    runs = summary["runs"]
    bits = [f"{summary['distance_km']} km", f"{runs} run{'s' if runs != 1 else ''}"]
    if summary.get("avg_hr"):
        bits.append(f"{summary['avg_hr']} bpm avg")
    return "- Running, last 7 days: " + ", ".join(bits)


def _alert_lines(alerts: list[dict]) -> list[str]:
    """Garmin high-HR alerts, listed so the user can say what each one was.

    These fire when heart rate crosses the user's threshold while the watch
    believes they are at rest, so the calendar rarely explains them. Listing
    the time and the reading is what lets the user recall it.
    """
    if not alerts:
        return []
    lines = ["", "**Heart rate alerts** — what was happening?"]
    for alert in alerts:
        threshold = alert.get("threshold")
        over = f" (over {threshold})" if threshold else ""
        lines.append(f"- {alert.get('time')} — {alert.get('bpm')} bpm{over}")
    return lines


def _activity_lines(activities: list[dict]) -> list[str]:
    """Render logged sessions. Steps cannot distinguish a 10k from a day of
    walking, so the sessions themselves are what make the day legible."""
    lines = []
    for activity in activities:
        # Only the parts this session actually recorded. A gym session has no
        # distance and a walk may have no heart rate; printing "None km" is
        # worse than printing nothing.
        bits = []
        if activity.get("distance_km"):
            bits.append(f"{activity['distance_km']} km")
        if activity.get("duration_min"):
            bits.append(f"{activity['duration_min']} min")
        if activity.get("avg_hr"):
            bits.append(f"{activity['avg_hr']} bpm avg")
        if activity.get("calories"):
            bits.append(f"{activity['calories']} cal")
        name = activity.get("name") or activity.get("type") or "Activity"
        suffix = "  🏅 PR" if activity.get("is_pr") else ""
        detail = f" — {', '.join(bits)}" if bits else ""
        lines.append(f"- Activity: {name}{detail}{suffix}")
    return lines


def _wellness_trend_section(events: list[dict]) -> list[str]:
    """Render normalised mood and energy readings in chronological order."""
    from pa_core.wellness import parse_scale

    readings = []
    for event in sorted(events, key=lambda e: (e.get("date", ""), e.get("timestamp", ""))):
        if event.get("category") != "wellness" or event.get("action") != "check_in":
            continue
        details = event.get("details", {})
        mood = parse_scale(details.get("mood_normalized", details.get("mood")))
        energy = parse_scale(details.get("energy_normalized", details.get("energy")))
        readings.append((mood, energy))

    moods = [m for m, _ in readings if m is not None]
    energies = [e for _, e in readings if e is not None]
    if not moods and not energies:
        return []

    def line(label: str, values: list[int]) -> str | None:
        if not values:
            return None
        direction = ""
        if len(values) > 1:
            if values[-1] > values[0]:
                direction = " (improving)"
            elif values[-1] < values[0]:
                direction = " (declining)"
            else:
                direction = " (steady)"
        return f"- {label}: {' -> '.join(map(str, values))}{direction}"

    lines = ["## 7-Day Mood and Energy\n"]
    lines.extend(value for value in (line("Mood", moods), line("Energy", energies)) if value)
    lines.append("")
    return lines


def _recent_events(date_str: str, days: int) -> list[dict]:
    """Load recent events and attach their log date for trend grouping."""
    end = datetime.strptime(date_str, "%Y-%m-%d").date()
    result = []
    for offset in range(days - 1, -1, -1):
        day = (end - timedelta(days=offset)).isoformat()
        result.extend({**event, "date": event.get("date", day)} for event in get_events(day))
    return result


def _format_event(ev: dict) -> str:
    """Format a single event with time and optional calendar label."""
    time_str = ev.get("start", "")
    if "T" in time_str:
        time_str = time_str.split("T")[1][:5]
    label = ev.get("calendar")
    label_str = f" [{label}]" if label else ""
    return f"- {time_str}{label_str} {ev.get('summary', 'No title')}"


def _calendar_section(date_str: str) -> list[str]:
    """Build Calendar section."""
    lines = ["## Calendar\n"]
    try:
        from pa_google.calendar import get_all_todays_events, get_all_upcoming_events

        today_events = get_all_todays_events()
        if today_events:
            lines.append("### Today")
            for ev in today_events:
                lines.append(_format_event(ev))
        else:
            lines.append("_No events today._")

        tomorrow_dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
        tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")
        tomorrow_events = get_all_upcoming_events(days=2)
        tomorrow_only = [
            ev for ev in tomorrow_events
            if tomorrow_str in ev.get("start", "")
        ]
        if tomorrow_only:
            lines.append(f"\n### Tomorrow ({tomorrow_str})")
            for ev in tomorrow_only:
                lines.append(_format_event(ev))
    except (ImportError, Exception) as exc:
        lines.append(f"_Calendar unavailable: {exc}_")
    lines.append("")
    return lines


def _focus_section(events: list[dict] | None = None) -> list[str]:
    """Build 'Today's Focus' — top 5 tasks sorted by urgency/due date."""
    lines = []
    planned = [
        event for event in (events or [])
        if event.get("category") == "task" and event.get("action") == "planned"
    ]
    if planned:
        lines.append("## Today's Focus\n")
        for event in planned[:5]:
            lines.append(f"- **Chosen plan:** {event.get('summary', 'Untitled')}")
        lines.append("")
        return lines

    try:
        from pa_notion.tasks import list_tasks

        open_tasks = list_tasks(status_filter="To Do")
        if not open_tasks:
            lines.append("## Today's Focus\n")
            lines.append("_No open tasks — nice work!_")
            lines.append("")
            return lines

        sorted_tasks = sorted(open_tasks, key=_task_sort_key)
        top = sorted_tasks[:5]
        total = len(open_tasks)
        projects = len(set(t.get("project", "") for t in open_tasks if t.get("project")))

        lines.append(f"## Today's Focus (top {len(top)} of {total} open tasks)\n")
        today = date.today().isoformat()
        for i, t in enumerate(top, 1):
            priority = t.get("priority", "")
            project = t.get("project", "")
            due = t.get("due_date", "")
            parts = []
            if priority:
                parts.append(f"[{priority}]")
            parts.append(t.get("title", "Untitled"))
            if due:
                if due < today:
                    parts.append(f"— **overdue** (due {due})")
                else:
                    parts.append(f"— due {due}")
            if project:
                parts.append(f"[{project}]")
            lines.append(f"{i}. {' '.join(parts)}")

        if total > 5:
            lines.append(f"\n_{total} open tasks across {projects} projects. Showing the top 5._")
    except (ImportError, Exception) as exc:
        lines.append("## Today's Focus\n")
        lines.append(f"_Tasks unavailable: {exc}_")
    lines.append("")
    return lines


def _format_links(event: dict) -> str:
    """Format resource links from an event as inline markdown."""
    links = event.get("links", {})
    if not links:
        return ""
    parts = [f"[{label}]({url})" for label, url in links.items()]
    return " — " + " | ".join(parts)


def _wins_section(events: list[dict]) -> list[str]:
    """Build Wins section — only if there are completed actions."""
    completed = []
    seen = set()
    for event in events:
        if event["action"] not in ("archived", "completed", "resolved", "created"):
            continue
        key = (event.get("action"), event.get("summary"), event.get("project"))
        if key in seen:
            continue
        seen.add(key)
        completed.append(event)
    if not completed:
        return []

    lines = ["## Wins So Far\n"]
    for e in completed:
        project_tag = f" [{e['project']}]" if e.get("project") else ""
        link_str = _format_links(e)
        lines.append(f"- **{e['action'].title()}**: {e['summary']}{project_tag}{link_str}")
    lines.append("")
    return lines


def _heads_up_section(events: list[dict]) -> list[str]:
    """Build Heads Up section — flagged items + info events. Skip if empty."""
    flagged = [e for e in events if e["action"] == "flagged"]
    info = [e for e in events if e["category"] == "info"]
    items = flagged + info
    if not items:
        return []

    lines = ["## Heads Up\n"]
    for e in items:
        link_str = _format_links(e)
        lines.append(f"- {e['summary']}{link_str}")
    lines.append("")
    return lines


def generate_briefing(date: str | None = None) -> str:
    """Generate a markdown daily briefing. Returns the markdown string."""
    date_str = date or _today_str()
    events = get_events(date_str)
    recent = _recent_events(date_str, 7)
    history = _recent_events(date_str, 30)

    try:
        from pa_core.context import _fetch_health
        health = _fetch_health(date_str)
    except Exception:
        health = {"ok": False}

    sections: list[str] = []
    name = get_assistant_name()
    sections.append(f"# {name} Daily Briefing — {date_str}\n")

    sections.extend(_wellness_section(events))
    sections.extend(_wellness_trend_section(recent))
    sections.extend(_health_section(health))
    sections.extend(_calendar_section(date_str))
    sections.extend(_focus_section(events))
    sections.extend(_habits_section(events, date_str, history=history))
    sections.extend(_gratitude_section(history))
    sections.extend(_wins_section(events))
    sections.extend(_heads_up_section(events))

    return "\n".join(sections)


def save_briefing(date: str | None = None) -> Path:
    """Generate and save the briefing to activity/briefings/. Returns the file path."""
    date = date or _today_str()
    content = generate_briefing(date)
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFINGS_DIR / f"{date}.md"
    with open(path, "w") as f:
        f.write(content)
    return path


# --- Evening Briefing ---


def _streak_count(habit_name: str, date_str: str) -> int:
    """Count consecutive days a habit was completed going backwards from date (exclusive)."""
    from pa_core.context import streak_count
    return streak_count(habit_name, date_str)


def _habits_section(
    events: list[dict], date_str: str, history: list[dict] | None = None
) -> list[str]:
    """Build Habits section — configured habits + freeform, with streaks."""
    config = get_user_config()
    configured_habits = config.get("habits", [])
    habit_events = [e for e in events if e["category"] == "habit"]
    history = history or [{**event, "date": event.get("date", date_str)} for event in events]

    if not configured_habits and not habit_events:
        return []

    lines = ["## Habits\n"]

    # Track which habit events are accounted for by configured habits
    matched_summaries = set()

    for habit in configured_habits:
        name = habit.get("name", "")
        emoji = habit.get("emoji", "")
        completed_event = next(
            (e for e in habit_events if e["summary"] == name and e["action"] == "completed"),
            None,
        )
        skipped_event = next(
            (e for e in habit_events if e["summary"] == name and e["action"] == "skipped"),
            None,
        )
        matched_summaries.add(name)

        if completed_event:
            note = completed_event.get("details", {}).get("note", "")
            duration = completed_event.get("details", {}).get("duration_min")
            detail_parts = []
            if duration:
                detail_parts.append(f"{duration} min")
            if note:
                detail_parts.append(note)
            detail_str = f' — "{", ".join(detail_parts)}"' if detail_parts else ""
            prefix = f"{emoji} " if emoji else ""
            lines.append(f"- {prefix}{name}{detail_str}")
        elif skipped_event:
            reason = skipped_event.get("details", {}).get("reason", "")
            reason_str = f" — {reason}" if reason else ""
            lines.append(f"- {name} — skipped{reason_str}")
        else:
            lines.append(f"- {name} — _not logged_")

    # Freeform habit events (not matching configured habits)
    freeform = [e for e in habit_events if e["summary"] not in matched_summaries and e["action"] == "completed"]
    for e in freeform:
        lines.append(f"- {e['summary']} (freeform)")

    # Cadence-aware streak and completion rate for every configured habit.
    from pa_core.wellness import completion_rate, streak

    for habit in configured_habits:
        name = habit.get("name", "")
        cadence = habit.get("cadence", "daily")
        target = int(habit.get("target", 1) or 1)
        period_label = {"daily": "days", "weekly": "weeks", "monthly": "months"}.get(
            cadence, "days"
        )
        periods = {"daily": 30, "weekly": 5, "monthly": 2}.get(cadence, 30)
        run = streak(name, history, cadence, target, today=date_str)
        done, total = completion_rate(
            name, history, cadence, target, today=date_str, lookback=periods
        )
        lines.append(
            f"- {name} stats: streak {run} {period_label} | "
            f"Completion: {done} of the last {total} {period_label}"
        )

    lines.append("")
    return lines


def _reflections_section(events: list[dict]) -> list[str]:
    """Build Reflections section from info/flagged events."""
    items = [e for e in events if e["category"] == "info" or e["action"] == "flagged"]
    if not items:
        return []
    lines = ["## Reflections\n"]
    for e in items:
        link_str = _format_links(e)
        lines.append(f"- {e['summary']}{link_str}")
    lines.append("")
    return lines


def _tomorrow_focus_section() -> list[str]:
    """Build Tomorrow's Focus — top 3 tasks."""
    lines = []
    try:
        from pa_notion.tasks import list_tasks

        open_tasks = list_tasks(status_filter="To Do")
        if not open_tasks:
            lines.append("## Tomorrow's Focus\n")
            lines.append("_No open tasks — enjoy the rest!_")
            lines.append("")
            return lines

        sorted_tasks = sorted(open_tasks, key=_task_sort_key)
        top = sorted_tasks[:3]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        lines.append("## Tomorrow's Focus\n")
        for i, t in enumerate(top, 1):
            priority = t.get("priority", "")
            project = t.get("project", "")
            due = t.get("due_date", "")
            parts = []
            if priority:
                parts.append(f"[{priority}]")
            parts.append(t.get("title", "Untitled"))
            if due:
                if due <= tomorrow:
                    parts.append(f"— **due {due}**")
                else:
                    parts.append(f"— due {due}")
            if project:
                parts.append(f"[{project}]")
            lines.append(f"{i}. {' '.join(parts)}")
    except (ImportError, Exception) as exc:
        lines.append("## Tomorrow's Focus\n")
        lines.append(f"_Tasks unavailable: {exc}_")
    lines.append("")
    return lines


def _gratitude_section(events: list[dict]) -> list[str]:
    """Build Gratitude section from wellness/gratitude events."""
    gratitude = [e for e in events if e["category"] == "wellness" and e["action"] == "gratitude"]
    if not gratitude:
        return ["## Gratitude\n", "_Not logged yet._", ""]
    lines = ["## Gratitude\n"]
    for e in gratitude:
        prefix = f"{e['date']}: " if e.get("date") else ""
        lines.append(f"- {prefix}{e['summary']}")
    lines.append("")
    return lines


def generate_evening_briefing(date: str | None = None) -> str:
    """Generate a markdown evening briefing. Returns the markdown string."""
    date_str = date or _today_str()
    events = get_events(date_str)
    history = _recent_events(date_str, 30)
    recent = _recent_events(date_str, 7)

    try:
        from pa_core.context import _fetch_health
        health = _fetch_health(date_str)
    except Exception:
        health = {"ok": False}

    sections: list[str] = []
    name = get_assistant_name()
    sections.append(f"# {name} Evening Briefing — {date_str}\n")

    sections.extend(_health_section(health))
    sections.extend(_wins_section(events))
    sections.extend(_wellness_trend_section(recent))
    sections.extend(_habits_section(events, date_str, history=history))
    sections.extend(_reflections_section(events))
    sections.extend(_tomorrow_focus_section())
    sections.extend(_gratitude_section(history))

    return "\n".join(sections)


def save_evening_briefing(date: str | None = None) -> Path:
    """Generate and save the evening briefing. Returns the file path."""
    date_str = date or _today_str()
    content = generate_evening_briefing(date_str)
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEFINGS_DIR / f"{date_str}-evening.md"
    with open(path, "w") as f:
        f.write(content)
    return path
