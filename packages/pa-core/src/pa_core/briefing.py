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


def _focus_section() -> list[str]:
    """Build 'Today's Focus' — top 5 tasks sorted by urgency/due date."""
    lines = []
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
    completed = [e for e in events if e["action"] in ("archived", "completed", "resolved", "created")]
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


def _sync_google_tasks():
    """Sync completed Google Tasks back to Notion, logging each as a win."""
    try:
        from pa_notion.tasks import sync_google_tasks
        from pa_core.daily_log import log_event
        synced = sync_google_tasks()
        for s in synced:
            log_event("task", "completed", f"Completed: {s['title']} (synced from Google Tasks)")
    except (ImportError, Exception):
        pass


def generate_briefing(date: str | None = None) -> str:
    """Generate a markdown daily briefing. Returns the markdown string."""
    _sync_google_tasks()
    date_str = date or _today_str()
    events = get_events(date_str)

    sections: list[str] = []
    name = get_assistant_name()
    sections.append(f"# {name} Daily Briefing — {date_str}\n")

    sections.extend(_wellness_section(events))
    sections.extend(_calendar_section(date_str))
    sections.extend(_focus_section())
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


def _habits_section(events: list[dict], date_str: str) -> list[str]:
    """Build Habits section — configured habits + freeform, with streaks."""
    config = get_user_config()
    configured_habits = config.get("habits", [])
    habit_events = [e for e in events if e["category"] == "habit"]

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

    # Streaks for completed configured habits
    streak_parts = []
    for habit in configured_habits:
        name = habit.get("name", "")
        completed_today = any(
            e["summary"] == name and e["action"] == "completed" for e in habit_events
        )
        if completed_today:
            streak = _streak_count(name, date_str) + 1  # +1 for today
        else:
            streak = 0
        if streak > 1:
            streak_parts.append(f"{name} {streak} days")

    if streak_parts:
        lines.append(f"\nStreak: {' | '.join(streak_parts)}")

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
        lines.append(f"- {e['summary']}")
    lines.append("")
    return lines


def generate_evening_briefing(date: str | None = None) -> str:
    """Generate a markdown evening briefing. Returns the markdown string."""
    _sync_google_tasks()
    date_str = date or _today_str()
    events = get_events(date_str)

    sections: list[str] = []
    name = get_assistant_name()
    sections.append(f"# {name} Evening Briefing — {date_str}\n")

    sections.extend(_wins_section(events))
    sections.extend(_habits_section(events, date_str))
    sections.extend(_reflections_section(events))
    sections.extend(_tomorrow_focus_section())
    sections.extend(_gratitude_section(events))

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
