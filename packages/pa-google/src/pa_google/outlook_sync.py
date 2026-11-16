"""One-way idempotent mirror: work Outlook calendar -> a Google "Day Job" calendar.

Outlook is the source of truth. Each synced Google event is stamped with
``extendedProperties.private.syncedFrom = "outlook"`` (so we only ever touch events we
created, never the user's own) and ``outlookKey`` (a stable subject+start key) so reruns
insert new events, patch changed ones, and delete events removed from Outlook.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pa_core.cli_runner import run_gws

from .calendar import _get_calendars
from .outlook import get_outlook_events

TARGET_LABEL = "Day Job"  # the Google calendar (by user.yaml label) we mirror Outlook into
SYNC_MARKER = "outlook"  # extendedProperties.private.syncedFrom
TIME_ZONE = "Europe/London"
_SYNC_NOTE = "Synced from Outlook by PA — edit in Outlook, not here."


class WorkCalendarNotConfigured(RuntimeError):
    """Raised when no calendar labelled 'Day Job' is configured in user.yaml."""


def _work_calendar_id() -> str:
    for cal in _get_calendars():
        if (cal.get("label") or "").strip().lower() == TARGET_LABEL.lower():
            return cal["id"]
    raise WorkCalendarNotConfigured(
        f"No calendar labelled '{TARGET_LABEL}' in user.yaml `calendars`. Add one (create it "
        "with `gws calendar calendars insert`) before syncing."
    )


def _event_body(ev: dict, time_zone: str = TIME_ZONE) -> dict:
    """Build the Google Calendar event resource for an Outlook event dict."""
    body: dict = {
        "summary": ev["summary"] or "(no title)",
        "description": _SYNC_NOTE,
        "extendedProperties": {"private": {"syncedFrom": SYNC_MARKER, "outlookKey": ev["key"]}},
    }
    if ev.get("location"):
        body["location"] = ev["location"]
    if ev.get("all_day"):
        start_date = ev["start"][:10]
        end_date = (datetime.fromisoformat(start_date) + timedelta(days=1)).date().isoformat()
        body["start"] = {"date": start_date}
        body["end"] = {"date": end_date}
    else:
        body["start"] = {"dateTime": ev["start"], "timeZone": time_zone}
        body["end"] = {"dateTime": ev["end"], "timeZone": time_zone}
    return body


def _sig_from_ev(ev: dict) -> str:
    if ev.get("all_day"):
        s, e = ev["start"][:10], ""
    else:
        s, e = ev["start"][:16], ev["end"][:16]
    return "|".join([(ev["summary"] or "").strip(), (ev.get("location") or "").strip(), s, e, str(bool(ev.get("all_day")))])


def _sig_from_google(item: dict) -> str:
    st, en = item.get("start", {}), item.get("end", {})
    all_day = "date" in st
    if all_day:
        s, e = (st.get("date") or "")[:10], ""
    else:
        s, e = (st.get("dateTime") or "")[:16], (en.get("dateTime") or "")[:16]
    return "|".join([(item.get("summary") or "").strip(), (item.get("location") or "").strip(), s, e, str(all_day)])


def _existing_index(items: list[dict]) -> dict:
    """Map outlookKey -> {id, sig} for our previously-synced Google events."""
    index: dict = {}
    for it in items:
        priv = (it.get("extendedProperties", {}) or {}).get("private", {}) or {}
        if priv.get("syncedFrom") != SYNC_MARKER:
            continue
        key = priv.get("outlookKey")
        if key:
            index[key] = {"id": it["id"], "sig": _sig_from_google(it)}
    return index


def _diff(outlook_events: list[dict], existing: dict):
    """Return (to_insert[ev], to_update[(id, ev)], to_delete[id])."""
    desired = set()
    to_insert, to_update = [], []
    for ev in outlook_events:
        key = ev["key"]
        desired.add(key)
        if key not in existing:
            to_insert.append(ev)
        elif existing[key]["sig"] != _sig_from_ev(ev):
            to_update.append((existing[key]["id"], ev))
    to_delete = [v["id"] for k, v in existing.items() if k not in desired]
    return to_insert, to_update, to_delete


def sync_outlook_to_google(days: int = 14) -> dict:
    """Mirror the next ``days`` of work Outlook events into the Google 'Work' calendar.

    Returns {added, updated, removed, total, calendar_id}. Raises OutlookError if Outlook
    can't be read, or WorkCalendarNotConfigured if no Work calendar is set up.
    """
    cal_id = _work_calendar_id()
    events = get_outlook_events(days=days)

    start_local = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    time_min = start_local.astimezone().isoformat()
    time_max = (start_local + timedelta(days=days)).astimezone().isoformat()

    listed = run_gws("calendar", "events", "list", {
        "calendarId": cal_id,
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "maxResults": 250,
        "privateExtendedProperty": f"syncedFrom={SYNC_MARKER}",
    }) or {}
    existing = _existing_index(listed.get("items", []))

    to_insert, to_update, to_delete = _diff(events, existing)

    for ev in to_insert:
        run_gws("calendar", "events", "insert", {"calendarId": cal_id}, body=_event_body(ev))
    for event_id, ev in to_update:
        run_gws("calendar", "events", "patch", {"calendarId": cal_id, "eventId": event_id}, body=_event_body(ev))
    for event_id in to_delete:
        run_gws("calendar", "events", "delete", {"calendarId": cal_id, "eventId": event_id})

    return {
        "added": len(to_insert),
        "updated": len(to_update),
        "removed": len(to_delete),
        "total": len(events),
        "calendar_id": cal_id,
    }
