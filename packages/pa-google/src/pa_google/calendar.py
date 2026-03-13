"""Calendar helpers — uses cli_runner to call gws CLI."""

from datetime import datetime, timedelta

from pa_core.cli_runner import run_gws


def get_todays_events() -> list[dict]:
    """Fetch today's calendar events."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    result = run_gws("calendar", "events", "list", {
        "calendarId": "primary",
        "timeMin": start_of_day.isoformat() + "Z",
        "timeMax": end_of_day.isoformat() + "Z",
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
        }
        for e in events
    ]


def get_upcoming_events(days: int = 7) -> list[dict]:
    """Fetch upcoming events for the next N days."""
    now = datetime.now()
    end = now + timedelta(days=days)

    result = run_gws("calendar", "events", "list", {
        "calendarId": "primary",
        "timeMin": now.isoformat() + "Z",
        "timeMax": end.isoformat() + "Z",
        "singleEvents": True,
        "orderBy": "startTime",
    })
    events = result.get("items", [])
    return [
        {
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
        }
        for e in events
    ]
