"""Calendar helpers — uses cli_runner to call gws CLI."""

import zoneinfo
from datetime import date, datetime, timedelta

from pa_core.cli_runner import run_gws
from pa_core.config import get_user_config


def _timezone_name() -> str:
    try:
        return get_user_config().get("timezone", "Europe/London")
    except Exception:
        return "Europe/London"


def _now() -> datetime:
    """Current time in the user's time zone, so API bounds carry the right offset."""
    return datetime.now(zoneinfo.ZoneInfo(_timezone_name()))


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
    return [_normalise(e, calendar_id, label) for e in events]


def _normalise(e: dict, calendar_id: str, label: str | None = None) -> dict:
    return {
        "id": e.get("id", ""),
        "calendar_id": calendar_id,
        "summary": e.get("summary", "(no title)"),
        "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
        "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
        "location": e.get("location", ""),
        "description": e.get("description", ""),
        "attendees": [a.get("email", "") for a in e.get("attendees", [])],
        "calendar": label,
        "link": e.get("htmlLink", ""),
    }


def _sort_events(events: list[dict]) -> list[dict]:
    """Sort events by start time."""
    return sorted(events, key=lambda e: e.get("start", ""))


def get_todays_events(calendar_id: str = "primary", label: str | None = None) -> list[dict]:
    """Fetch today's calendar events from a single calendar."""
    start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    return _fetch_events(calendar_id, start_of_day.isoformat(), end_of_day.isoformat(), label)


def get_upcoming_events(days: int = 7, calendar_id: str = "primary", label: str | None = None) -> list[dict]:
    """Fetch upcoming events for the next N days from a single calendar."""
    now = _now()
    end = now + timedelta(days=days)
    return _fetch_events(calendar_id, now.isoformat(), end.isoformat(), label)


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
    start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    for cal in calendars:
        entry = {"id": cal["id"], "label": cal.get("label")}
        try:
            events = _fetch_events(
                cal["id"],
                start_of_day.isoformat(),
                end_of_day.isoformat(),
                cal.get("label"),
            )
            entry["status"] = "OK"
            entry["event_count"] = len(events)
        except Exception as e:
            entry["status"] = f"ERROR: {e}"
            entry["event_count"] = 0
        results.append(entry)
    return results


def resolve_calendar(calendar: str | None) -> str:
    """Map a calendar label from user.yaml (any case) to its id. Unknown values pass through as ids."""
    if not calendar:
        return "primary"
    for cal in _get_calendars():
        if (cal.get("label") or "").lower() == calendar.lower():
            return cal["id"]
    return calendar


def _when(value: str) -> dict:
    """Event time body: a date for YYYY-MM-DD, otherwise a local dateTime in the user's zone."""
    if len(value) == 10:
        return {"date": date.fromisoformat(value).isoformat()}
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo:
        return {"dateTime": parsed.isoformat()}
    return {"dateTime": parsed.isoformat(timespec="seconds"), "timeZone": _timezone_name()}


def _default_end(start: str) -> str:
    if len(start) == 10:
        return (date.fromisoformat(start) + timedelta(days=1)).isoformat()
    return (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()


def get_event(event_id: str, calendar: str | None = None) -> dict:
    calendar_id = resolve_calendar(calendar)
    raw = run_gws("calendar", "events", "get", {"calendarId": calendar_id, "eventId": event_id})
    return _normalise(raw, calendar_id)


def add_event(
    title: str,
    start: str,
    end: str | None = None,
    *,
    calendar: str | None = None,
    location: str = "",
    description: str = "",
    attendees: list[str] | None = None,
) -> dict:
    """Create an event and return it as re-fetched from Google.

    `start`/`end` are YYYY-MM-DD for all-day events or ISO date-times. A missing end
    means the next day (all-day) or one hour later. Google assigns the event id.
    """
    end = end or _default_end(start)
    if end <= start:
        raise ValueError(f"End {end} must be after start {start}")
    calendar_id = resolve_calendar(calendar)
    body: dict = {"summary": title, "start": _when(start), "end": _when(end)}
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    created = run_gws("calendar", "events", "insert", {"calendarId": calendar_id}, body=body)
    return get_event(created["id"], calendar_id)


def update_event(
    event_id: str,
    *,
    calendar: str | None = None,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> dict:
    """Patch only the given fields, then return the event as re-fetched from Google."""
    calendar_id = resolve_calendar(calendar)
    body: dict = {}
    if title is not None:
        body["summary"] = title
    if start is not None:
        body["start"] = _when(start)
    if end is not None:
        body["end"] = _when(end)
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description
    if not body:
        raise ValueError("Nothing to update")
    run_gws("calendar", "events", "patch", {"calendarId": calendar_id, "eventId": event_id}, body=body)
    return get_event(event_id, calendar_id)


def delete_event(event_id: str, calendar: str | None = None) -> None:
    run_gws("calendar", "events", "delete", {"calendarId": resolve_calendar(calendar), "eventId": event_id})
