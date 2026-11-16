"""Tests for pa_google.outlook_sync — idempotent Outlook -> Google 'Work' calendar mirror."""

from unittest.mock import patch

import pytest

from pa_google import outlook_sync as s


def _ev(subject, start, end, location="", all_day=False):
    return {"key": f"{subject}|{start}", "summary": subject, "start": start, "end": end,
            "location": location, "all_day": all_day}


def test_event_body_timed():
    b = s._event_body(_ev("Standup", "2026-06-17T09:00:00", "2026-06-17T09:30:00", "Teams"))
    assert b["summary"] == "Standup"
    assert b["start"] == {"dateTime": "2026-06-17T09:00:00", "timeZone": "Europe/London"}
    assert b["location"] == "Teams"
    assert b["extendedProperties"]["private"]["syncedFrom"] == "outlook"
    assert b["extendedProperties"]["private"]["outlookKey"] == "Standup|2026-06-17T09:00:00"


def test_event_body_all_day_uses_exclusive_end_date():
    b = s._event_body(_ev("Leave", "2026-06-20T00:00:00", "2026-06-20T00:00:00", all_day=True))
    assert b["start"] == {"date": "2026-06-20"}
    assert b["end"] == {"date": "2026-06-21"}


def test_sig_matches_between_ev_and_its_google_body():
    """An unchanged event must produce equal signatures (no spurious update)."""
    ev = _ev("PDR", "2026-06-17T14:30:00", "2026-06-17T15:15:00", "Teams")
    google_item = {
        "summary": "PDR", "location": "Teams",
        "start": {"dateTime": "2026-06-17T14:30:00+01:00"},
        "end": {"dateTime": "2026-06-17T15:15:00+01:00"},
    }
    assert s._sig_from_ev(ev) == s._sig_from_google(google_item)


def test_diff_insert_update_delete():
    existing = {
        "Keep|2026-06-17T09:00:00": {"id": "g1", "sig": s._sig_from_ev(_ev("Keep", "2026-06-17T09:00:00", "2026-06-17T09:30:00"))},
        "Changed|2026-06-18T10:00:00": {"id": "g2", "sig": "STALE-SIG"},
        "Gone|2026-06-19T11:00:00": {"id": "g3", "sig": "whatever"},
    }
    outlook_events = [
        _ev("Keep", "2026-06-17T09:00:00", "2026-06-17T09:30:00"),     # unchanged
        _ev("Changed", "2026-06-18T10:00:00", "2026-06-18T10:30:00"),  # sig differs -> update
        _ev("New", "2026-06-20T12:00:00", "2026-06-20T12:30:00"),      # insert
    ]
    ins, upd, dele = s._diff(outlook_events, existing)
    assert [e["summary"] for e in ins] == ["New"]
    assert [eid for eid, _ in upd] == ["g2"]
    assert dele == ["g3"]


def test_existing_index_ignores_non_synced_events():
    items = [
        {"id": "a", "extendedProperties": {"private": {"syncedFrom": "outlook", "outlookKey": "K|t"}},
         "summary": "x", "start": {"dateTime": "2026-06-17T09:00:00+01:00"}, "end": {"dateTime": "2026-06-17T09:30:00+01:00"}},
        {"id": "b", "summary": "manual event the user made"},  # no marker -> must be ignored
    ]
    idx = s._existing_index(items)
    assert list(idx.keys()) == ["K|t"]
    assert idx["K|t"]["id"] == "a"


def test_sync_orchestration_calls_insert_update_delete():
    outlook_events = [
        _ev("New", "2026-06-20T12:00:00", "2026-06-20T12:30:00"),
        _ev("Changed", "2026-06-18T10:00:00", "2026-06-18T10:30:00"),
    ]
    listed = {"items": [
        {"id": "g2", "extendedProperties": {"private": {"syncedFrom": "outlook", "outlookKey": "Changed|2026-06-18T10:00:00"}},
         "summary": "Changed", "start": {"dateTime": "2026-06-18T09:00:00+01:00"}, "end": {"dateTime": "2026-06-18T09:30:00+01:00"}},
        {"id": "g3", "extendedProperties": {"private": {"syncedFrom": "outlook", "outlookKey": "Removed|2026-06-19T11:00:00"}},
         "summary": "Removed", "start": {"dateTime": "2026-06-19T11:00:00+01:00"}, "end": {"dateTime": "2026-06-19T11:30:00+01:00"}},
    ]}
    calls = []

    def fake_run_gws(service, resource, method, params=None, *, body=None, **kw):
        calls.append((method, params, body))
        if method == "list":
            return listed
        return {"id": "new"}

    with patch("pa_google.outlook_sync.get_outlook_events", return_value=outlook_events), \
         patch("pa_google.outlook_sync._work_calendar_id", return_value="WORKCAL"), \
         patch("pa_google.outlook_sync.run_gws", side_effect=fake_run_gws):
        res = s.sync_outlook_to_google(days=14)

    methods = [c[0] for c in calls]
    assert methods.count("insert") == 1
    assert methods.count("patch") == 1
    assert methods.count("delete") == 1
    assert res == {"added": 1, "updated": 1, "removed": 1, "total": 2, "calendar_id": "WORKCAL"}


def test_work_calendar_not_configured_raises():
    with patch("pa_google.outlook_sync._get_calendars", return_value=[{"id": "primary", "label": None}]):
        with pytest.raises(s.WorkCalendarNotConfigured):
            s._work_calendar_id()
