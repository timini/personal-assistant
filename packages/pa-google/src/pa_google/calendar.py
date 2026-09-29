"""Calendar helpers — uses cli_runner to call gws CLI."""

from datetime import datetime, timedelta

from pa_core.cli_runner import run_gws
from pa_core.config import get_user_config


def _get_calendars() -> list[dict]:
    """Read calendars from user.yaml, fall back to primary-only."""
    try:
        config = get_user_config()
        calendars = config.get("calendars")
        if calendars:
            return calendars
    except Exception:
        pass
    return [{"id": "primary", "label": None}]


def _fetch_events(calendar_id: str, time_min: str, time_max: str, label: str | None = None) -> list[dict]:
    """Fetch events from a single calendar, adding calendar label to each event."""
    result = run_gws("calendar", "events", "list", {
        "calendarId": calendar_id,
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
    })
    events = result.get("items", [])
    return [
        {
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "location": e.get("location", ""),
            "attendees": [a.get("email", "") for a in e.get("attendees", [])],
            "calendar": label,
        }
        for e in events
    ]


def _sort_events(events: list[dict]) -> list[dict]:
    """Sort events by start time."""
    return sorted(events, key=lambda e: e.get("start", ""))


def get_todays_events(calendar_id: str = "primary", label: str | None = None) -> list[dict]:
    """Fetch today's calendar events from a single calendar."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    return _fetch_events(
        calendar_id,
        start_of_day.isoformat() + "Z",
        end_of_day.isoformat() + "Z",
        label,
    )


def get_upcoming_events(days: int = 7, calendar_id: str = "primary", label: str | None = None) -> list[dict]:
    """Fetch upcoming events for the next N days from a single calendar."""
    now = datetime.now()
    end = now + timedelta(days=days)
    return _fetch_events(
        calendar_id,
        now.isoformat() + "Z",
        end.isoformat() + "Z",
        label,
    )


def get_all_todays_events() -> list[dict]:
    """Fetch today's events from all configured calendars, merged and sorted."""
    calendars = _get_calendars()
    all_events = []
    for cal in calendars:
        try:
            events = get_todays_events(calendar_id=cal["id"], label=cal.get("label"))
            all_events.extend(events)
        except Exception:
            # Skip calendars that fail (e.g. placeholder IDs)
            continue
    return _sort_events(all_events)


def get_all_upcoming_events(days: int = 7) -> list[dict]:
    """Fetch upcoming events from all configured calendars, merged and sorted."""
    calendars = _get_calendars()
    all_events = []
    for cal in calendars:
        try:
            events = get_upcoming_events(days=days, calendar_id=cal["id"], label=cal.get("label"))
            all_events.extend(events)
        except Exception:
            continue
    return _sort_events(all_events)


def check_calendars() -> list[dict]:
    """Check all configured calendars, return status and event counts."""
    calendars = _get_calendars()
    results = []
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    for cal in calendars:
        entry = {"id": cal["id"], "label": cal.get("label")}
        try:
            events = _fetch_events(
                cal["id"],
                start_of_day.isoformat() + "Z",
                end_of_day.isoformat() + "Z",
                cal.get("label"),
            )
            entry["status"] = "OK"
            entry["event_count"] = len(events)
        except Exception as e:
            entry["status"] = f"ERROR: {e}"
            entry["event_count"] = 0
        results.append(entry)
    return results
