"""Aggregate today's context — date, calendar, emails, tasks, habits, weather, stats."""

from datetime import datetime, timedelta
from pathlib import Path

from pa_core.config import get_now, get_user_config
from pa_core.daily_log import get_events

# WMO weather code → human description
_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
    82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def streak_count(habit_name: str, date_str: str) -> int:
    """Count consecutive days a habit was completed going backwards from date (exclusive).

    Looks back up to 30 days. Used by both context and evening briefing.
    """
    streak = 0
    current = datetime.strptime(date_str, "%Y-%m-%d").date()
    for _ in range(30):
        current -= timedelta(days=1)
        day_events = get_events(current.isoformat())
        completed = any(
            e["category"] == "habit"
            and e["action"] == "completed"
            and e["summary"] == habit_name
            for e in day_events
        )
        if completed:
            streak += 1
        else:
            break
    return streak


def _task_streak(date_str: str) -> int:
    """Count consecutive days with at least 1 task completed, going backwards from date (exclusive)."""
    streak = 0
    current = datetime.strptime(date_str, "%Y-%m-%d").date()
    for _ in range(30):
        current -= timedelta(days=1)
        day_events = get_events(current.isoformat())
        has_task = any(
            e["category"] == "task" and e["action"] in ("completed", "created")
            for e in day_events
        )
        if has_task:
            streak += 1
        else:
            break
    return streak


def _count_completed(date_str: str, days_back: int) -> int:
    """Count task completion events across N days of daily logs ending at date_str."""
    total = 0
    current = datetime.strptime(date_str, "%Y-%m-%d").date()
    for i in range(days_back):
        d = current - timedelta(days=i)
        events = get_events(d.isoformat())
        total += sum(
            1 for e in events
            if e["category"] == "task" and e["action"] in ("completed", "created")
        )
    return total


def _fetch_weather() -> dict:
    """Fetch current weather via IP geolocation + Open-Meteo. No API key needed."""
    import httpx

    # Step 1: IP geolocation
    geo = httpx.get("https://ipapi.co/json/", timeout=5).json()
    lat = geo.get("latitude")
    lon = geo.get("longitude")
    location = geo.get("city", "Unknown")

    # Step 2: Open-Meteo forecast
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    weather = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=5).json()

    current = weather.get("current", {})
    daily = weather.get("daily", {})

    return {
        "location": location,
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "description": _WMO_CODES.get(current.get("weather_code", -1), "Unknown"),
        "wind_speed": current.get("wind_speed_10m"),
        "high": daily.get("temperature_2m_max", [None])[0],
        "low": daily.get("temperature_2m_min", [None])[0],
        "rain_probability": daily.get("precipitation_probability_max", [0])[0],
    }


def _fetch_calendar() -> list[dict]:
    """Fetch today's calendar events."""
    from pa_google.calendar import get_all_todays_events

    events = get_all_todays_events()
    result = []
    for ev in events:
        time_str = ev.get("start", "")
        if "T" in time_str:
            time_str = time_str.split("T")[1][:5]
        result.append({
            "time": time_str,
            "summary": ev.get("summary", "No title"),
            "calendar": ev.get("calendar"),
        })
    return result


def _fetch_emails() -> list[dict]:
    """Fetch unread inbox emails."""
    from pa_google.gmail import get_inbox_emails

    emails = get_inbox_emails(limit=20, unread_only=True)
    return [
        {
            "from": e.get("from", ""),
            "subject": e.get("subject", ""),
            "snippet": e.get("snippet", ""),
            "id": e.get("id", ""),
        }
        for e in emails
    ]


def _fetch_tasks() -> tuple[list[dict], list[dict]]:
    """Fetch tasks due soon (7 days) and urgent tasks. Returns (due_soon, urgent)."""
    from datetime import date

    from pa_notion.tasks import list_tasks

    all_tasks = list_tasks()
    open_tasks = [t for t in all_tasks if t.get("status") not in ("Done",)]
    today = date.today()
    week_ahead = (today + timedelta(days=7)).isoformat()
    today_str = today.isoformat()

    due_soon = [
        t for t in open_tasks
        if t.get("due_date") and today_str <= t["due_date"] <= week_ahead
    ]
    due_soon.sort(key=lambda t: t.get("due_date", ""))

    urgent = [t for t in open_tasks if t.get("priority") == "Urgent"]

    return due_soon, urgent


def _fetch_habits(date_str: str) -> list[dict]:
    """Fetch habit status for today from user.yaml config and daily log."""
    config = get_user_config()
    configured_habits = config.get("habits", [])
    if not configured_habits:
        return []

    day_events = get_events(date_str)
    habit_events = [e for e in day_events if e["category"] == "habit"]

    habits = []
    for habit in configured_habits:
        name = habit.get("name", "")
        emoji = habit.get("emoji", "")

        completed = any(
            e["summary"] == name and e["action"] == "completed" for e in habit_events
        )
        skipped = any(
            e["summary"] == name and e["action"] == "skipped" for e in habit_events
        )

        if completed:
            s = streak_count(name, date_str) + 1  # +1 for today
            status = "completed"
        elif skipped:
            s = 0
            status = "skipped"
        else:
            s = 0
            status = "not_logged"

        habits.append({
            "name": name,
            "emoji": emoji,
            "streak": s,
            "logged_today": completed or skipped,
            "status": status,
        })

    return habits


def _fetch_completed(date_str: str) -> list[dict]:
    """Get task completion events from daily log for a given date."""
    events = get_events(date_str)
    return [
        e for e in events
        if e["category"] == "task" and e["action"] in ("completed", "created")
    ]


def _fetch_stats(date_str: str) -> dict:
    """Compute task completion stats."""
    today_count = _count_completed(date_str, 1)

    yesterday = (datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    yesterday_count = _count_completed(yesterday, 1)

    count_7d = _count_completed(date_str, 7)
    count_30d = _count_completed(date_str, 30)

    return {
        "completed_today_count": today_count,
        "completed_yesterday_count": yesterday_count,
        "completed_7d_count": count_7d,
        "completed_30d_count": count_30d,
        "avg_daily_7d": round(count_7d / 7, 1),
        "avg_daily_30d": round(count_30d / 30, 1),
        "task_streak": _task_streak(date_str),
    }


def get_today_context() -> dict:
    """Aggregate all of today's context into a single dict.

    Each data source is fetched independently with graceful error handling.
    """
    now = get_now()
    date_str = now["date"]
    errors = []

    # Calendar
    try:
        calendar = _fetch_calendar()
    except Exception as exc:
        calendar = []
        errors.append(f"Calendar: {exc}")

    # Emails
    try:
        emails = _fetch_emails()
    except Exception as exc:
        emails = []
        errors.append(f"Email: {exc}")

    # Tasks
    try:
        tasks_due_soon, tasks_urgent = _fetch_tasks()
    except Exception as exc:
        tasks_due_soon, tasks_urgent = [], []
        errors.append(f"Tasks: {exc}")

    # Completed today/yesterday
    try:
        completed_today = _fetch_completed(date_str)
        yesterday = (datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
        completed_yesterday = _fetch_completed(yesterday)
    except Exception as exc:
        completed_today, completed_yesterday = [], []
        errors.append(f"Daily log: {exc}")

    # Stats
    try:
        stats = _fetch_stats(date_str)
    except Exception as exc:
        stats = {
            "completed_today_count": 0, "completed_yesterday_count": 0,
            "completed_7d_count": 0, "completed_30d_count": 0,
            "avg_daily_7d": 0.0, "avg_daily_30d": 0.0, "task_streak": 0,
        }
        errors.append(f"Stats: {exc}")

    # Habits
    try:
        habits = _fetch_habits(date_str)
    except Exception as exc:
        habits = []
        errors.append(f"Habits: {exc}")

    # Weather
    try:
        weather = _fetch_weather()
    except Exception as exc:
        weather = {"location": "Unknown", "temperature": None, "feels_like": None,
                   "description": "Unavailable", "rain_probability": 0,
                   "high": None, "low": None, "wind_speed": None}
        errors.append(f"Weather: {exc}")

    return {
        "now": now,
        "calendar": calendar,
        "emails": emails,
        "tasks_due_soon": tasks_due_soon,
        "tasks_urgent": tasks_urgent,
        "completed_today": completed_today,
        "completed_yesterday": completed_yesterday,
        "stats": stats,
        "habits": habits,
        "weather": weather,
        "errors": errors,
    }


def render_context(ctx: dict) -> str:
    """Render context dict to markdown using Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("context.md.j2")
    return template.render(**ctx)
