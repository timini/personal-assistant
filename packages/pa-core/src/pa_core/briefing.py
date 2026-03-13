"""Generate daily briefing from event log, calendar, and tasks."""

from collections import Counter
from datetime import datetime
from pathlib import Path

from pa_core.config import PA_ROOT
from pa_core.daily_log import get_events, _today_str

BRIEFINGS_DIR = PA_ROOT / "activity" / "briefings"


def generate_briefing(date: str | None = None) -> str:
    """Generate a markdown daily briefing. Returns the markdown string."""
    date = date or _today_str()
    events = get_events(date)

    sections = []
    sections.append(f"# Daily Briefing — {date}\n")

    # 1. Wins & Accomplishments
    completed = [e for e in events if e["action"] in ("archived", "completed", "resolved", "created")]
    sections.append("## Wins & Accomplishments\n")
    if completed:
        for e in completed:
            project_tag = f" [{e['project']}]" if e.get("project") else ""
            sections.append(f"- **{e['action'].title()}**: {e['summary']}{project_tag}")
    else:
        sections.append("_No actions logged yet today._")
    sections.append("")

    # 2. New Tasks Created
    new_tasks = [e for e in events if e["category"] == "task" and e["action"] == "created"]
    sections.append("## New Tasks Created\n")
    if new_tasks:
        for e in new_tasks:
            project_tag = f" [{e['project']}]" if e.get("project") else ""
            sections.append(f"- {e['summary']}{project_tag}")
    else:
        sections.append("_No new tasks created today._")
    sections.append("")

    # 3. Calendar (lazy import pa-google)
    sections.append("## Calendar\n")
    try:
        from pa_google.calendar import get_todays_events, get_upcoming_events
        today_events = get_todays_events()
        if today_events:
            sections.append("### Today")
            for ev in today_events:
                time_str = ev.get("start", "")
                if "T" in time_str:
                    time_str = time_str.split("T")[1][:5]
                sections.append(f"- {time_str} {ev.get('summary', 'No title')}")
        else:
            sections.append("_No events today._")

        tomorrow_events = get_upcoming_events(days=2)
        from datetime import timedelta
        tomorrow_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        tomorrow_str = tomorrow_dt.strftime("%Y-%m-%d")
        tomorrow_only = [
            ev for ev in tomorrow_events
            if tomorrow_str in ev.get("start", "")
        ]
        if tomorrow_only:
            sections.append(f"\n### Tomorrow ({tomorrow_str})")
            for ev in tomorrow_only:
                time_str = ev.get("start", "")
                if "T" in time_str:
                    time_str = time_str.split("T")[1][:5]
                sections.append(f"- {time_str} {ev.get('summary', 'No title')}")
    except (ImportError, Exception) as exc:
        sections.append(f"_Calendar unavailable: {exc}_")
    sections.append("")

    # 4. Important Info
    info_events = [e for e in events if e["category"] == "info"]
    sections.append("## Important Info\n")
    if info_events:
        for e in info_events:
            sections.append(f"- {e['summary']}")
    else:
        sections.append("_No important info surfaced today._")
    sections.append("")

    # 5. Outstanding Items (lazy import pa-notion)
    sections.append("## Outstanding Items\n")
    flagged = [e for e in events if e["action"] == "flagged"]
    if flagged:
        sections.append("### Flagged Today")
        for e in flagged:
            sections.append(f"- {e['summary']}")
        sections.append("")

    try:
        from pa_notion.tasks import list_tasks
        open_tasks = list_tasks(status_filter="To Do")
        if open_tasks:
            sections.append("### Open Notion Tasks (To Do)")
            for t in open_tasks[:15]:
                priority = t.get("priority", "")
                project = t.get("project", "")
                due = t.get("due_date", "")
                tags = " | ".join(filter(None, [priority, project, due]))
                tag_str = f" ({tags})" if tags else ""
                sections.append(f"- {t.get('title', 'Untitled')}{tag_str}")
            if len(open_tasks) > 15:
                sections.append(f"- _...and {len(open_tasks) - 15} more_")
    except (ImportError, Exception) as exc:
        sections.append(f"_Tasks unavailable: {exc}_")
    sections.append("")

    # 6. Stats
    session_ids = set(e["session_id"] for e in events)
    cat_counts = Counter(e["category"] for e in events)
    sections.append("## Stats\n")
    sections.append(f"- **Events logged**: {len(events)}")
    sections.append(f"- **Sessions**: {len(session_ids)}")
    if cat_counts:
        breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(cat_counts.items()))
        sections.append(f"- **By category**: {breakdown}")
    sections.append("")

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
