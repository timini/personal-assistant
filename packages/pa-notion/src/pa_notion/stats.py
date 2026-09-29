"""Task stats computation and ASCII bar chart rendering."""

from collections import Counter
from datetime import datetime, timedelta

from pa_notion.tasks import list_tasks


def get_task_stats(today: str | None = None) -> dict:
    """Fetch all tasks and compute stats.

    Args:
        today: Override date string (YYYY-MM-DD) for testing. Defaults to today.
    """
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    cutoff_7d = (today_dt - timedelta(days=7)).isoformat()
    cutoff_30d = (today_dt - timedelta(days=30)).isoformat()

    tasks = list_tasks()

    # Status counts
    by_status: dict[str, int] = Counter()
    active_by_project: dict[str, int] = Counter()
    completed_by_day: dict[str, int] = Counter()
    completed_by_project_7d: dict[str, int] = Counter()
    completed_by_project_30d: dict[str, int] = Counter()

    done_count = 0
    active_count = 0

    for t in tasks:
        status = t.get("status", "")
        project = t.get("project", "") or "(no project)"
        by_status[status] += 1

        if status == "Done":
            done_count += 1
            edited = t.get("last_edited_time", "")
            if edited:
                edit_date = edited[:10]  # "2026-03-20T..." → "2026-03-20"
                if edit_date >= cutoff_7d[:10]:
                    completed_by_day[edit_date] += 1
                    completed_by_project_7d[project] += 1
                if edit_date >= cutoff_30d[:10]:
                    completed_by_project_30d[project] += 1
        else:
            active_count += 1
            active_by_project[project] += 1

    # Build 7-day daily breakdown
    completed_last_7d = []
    for i in range(7, 0, -1):
        d = today_dt - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_name = d.strftime("%a")
        completed_last_7d.append({
            "date": date_str,
            "day": day_name,
            "count": completed_by_day.get(date_str, 0),
        })

    return {
        "by_status": dict(by_status),
        "active_by_project": dict(active_by_project),
        "completed_last_7d": completed_last_7d,
        "completed_by_project_7d": dict(completed_by_project_7d),
        "completed_by_project_30d": dict(completed_by_project_30d),
        "total": len(tasks),
        "active": active_count,
        "done": done_count,
    }


def render_bar(label: str, value: int, max_value: int, width: int = 30) -> str:
    """Single horizontal bar: 'Label         ████████░░░░ 24'"""
    if max_value > 0:
        filled = round(value / max_value * width)
    else:
        filled = 0
    bar = "\u2588" * filled
    return f"  {label:<22s} {bar:<{width}s} {value}"


def render_stats(stats: dict) -> str:
    """Full ASCII report with all charts."""
    lines: list[str] = []

    # Summary
    lines.append(f"Total: {stats['total']}  Active: {stats['active']}  Done: {stats['done']}")
    lines.append("")

    # Tasks by Status
    lines.append("Tasks by Status")
    max_status = max(stats["by_status"].values()) if stats["by_status"] else 1
    for status in ["To Do", "In Progress", "Waiting", "Done"]:
        count = stats["by_status"].get(status, 0)
        if count > 0:
            lines.append(render_bar(status, count, max_status))
    lines.append("")

    # Tasks by Project (active)
    lines.append("Tasks by Project (active)")
    sorted_projects = sorted(stats["active_by_project"].items(), key=lambda x: -x[1])
    max_proj = sorted_projects[0][1] if sorted_projects else 1
    for project, count in sorted_projects:
        lines.append(render_bar(project, count, max_proj))
    lines.append("")

    # Completed last 7 days
    lines.append("Completed last 7 days")
    max_daily = max((d["count"] for d in stats["completed_last_7d"]), default=1) or 1
    for d in stats["completed_last_7d"]:
        label = f"{d['day']} {d['date'][5:]}"  # "Mon 03-17"
        lines.append(render_bar(label, d["count"], max_daily))
    lines.append("")

    # Completed by project (7 days)
    lines.append("Completed by project (7 days)")
    sorted_7d = sorted(stats["completed_by_project_7d"].items(), key=lambda x: -x[1])
    max_7d = sorted_7d[0][1] if sorted_7d else 1
    for project, count in sorted_7d:
        lines.append(render_bar(project, count, max_7d))
    lines.append("")

    # Completed by project (30 days)
    lines.append("Completed by project (30 days)")
    sorted_30d = sorted(stats["completed_by_project_30d"].items(), key=lambda x: -x[1])
    max_30d = sorted_30d[0][1] if sorted_30d else 1
    for project, count in sorted_30d:
        lines.append(render_bar(project, count, max_30d))

    return "\n".join(lines)
