"""Tests for calendar reads (ids, time zones) and event writes."""

from datetime import datetime
from unittest.mock import patch

import pytest

from pa_google import calendar
from pa_google.calendar import (
    add_event,
    delete_event,
    get_todays_events,
    resolve_calendar,
    update_event,
)

CALENDARS = [{"id": "primary", "label": None}, {"id": "fam@group", "label": "Family"}]
CONFIG = {"timezone": "Europe/London", "calendars": CALENDARS}


@pytest.fixture(autouse=True)
def _config():
    with patch("pa_google.calendar.get_user_config", return_value=CONFIG):
        yield


def _raw(event_id="ev1", start=None, end=None, summary="Dentist"):
    return {
        "id": event_id, "summary": summary, "htmlLink": "https://calendar.google.com/x",
        "description": "Bring card", "location": "Clinic",
        "start": start or {"dateTime": "2026-11-02T09:00:00Z"},
        "end": end or {"dateTime": "2026-11-02T09:30:00Z"},
    }


@patch("pa_google.calendar.run_gws")
def test_listed_events_carry_id_calendar_and_link(mock_gws):
    mock_gws.return_value = {"items": [_raw()]}
    event = get_todays_events(calendar_id="fam@group", label="Family")[0]
    assert event["id"] == "ev1"
    assert event["calendar_id"] == "fam@group"
    assert event["link"] == "https://calendar.google.com/x"
    assert event["description"] == "Bring card"


@patch("pa_google.calendar.run_gws")
def test_today_window_is_local_midnight_with_an_offset(mock_gws):
    mock_gws.return_value = {"items": []}
    get_todays_events()
    params = mock_gws.call_args.args[3]
    start = datetime.fromisoformat(params["timeMin"])
    assert start.tzinfo is not None
    assert (start.hour, start.minute) == (0, 0)
    assert not params["timeMin"].endswith("Z") or "+" not in params["timeMin"]


def test_resolve_calendar_by_label_id_or_default():
    assert resolve_calendar(None) == "primary"
    assert resolve_calendar("family") == "fam@group"
    assert resolve_calendar("someone@group") == "someone@group"


@patch("pa_google.calendar.run_gws")
def test_add_timed_event_sends_zone_and_verifies(mock_gws):
    mock_gws.side_effect = [{"id": "new1"}, _raw("new1")]
    event = add_event("Dentist", "2026-11-02T09:00", end="2026-11-02T09:30",
                      calendar="Family", location="Clinic")
    insert = mock_gws.call_args_list[0]
    assert insert.args[:3] == ("calendar", "events", "insert")
    assert insert.args[3] == {"calendarId": "fam@group"}
    body = insert.kwargs["body"]
    assert "id" not in body
    assert body["start"] == {"dateTime": "2026-11-02T09:00:00", "timeZone": "Europe/London"}
    assert body["end"] == {"dateTime": "2026-11-02T09:30:00", "timeZone": "Europe/London"}
    assert mock_gws.call_args_list[1].args[2] == "get"
    assert event["id"] == "new1"


@patch("pa_google.calendar.run_gws")
def test_add_all_day_event_ends_next_day(mock_gws):
    mock_gws.side_effect = [{"id": "d1"}, _raw("d1", {"date": "2026-11-02"}, {"date": "2026-11-03"})]
    add_event("Inset day", "2026-11-02")
    body = mock_gws.call_args_list[0].kwargs["body"]
    assert body["start"] == {"date": "2026-11-02"}
    assert body["end"] == {"date": "2026-11-03"}


@patch("pa_google.calendar.run_gws")
def test_add_timed_event_defaults_to_one_hour(mock_gws):
    mock_gws.side_effect = [{"id": "x"}, _raw("x")]
    add_event("Call", "2026-11-02T14:00")
    body = mock_gws.call_args_list[0].kwargs["body"]
    assert body["end"]["dateTime"] == "2026-11-02T15:00:00"


@patch("pa_google.calendar.run_gws")
def test_add_event_with_attendees(mock_gws):
    mock_gws.side_effect = [{"id": "x"}, _raw("x")]
    add_event("Call", "2026-11-02T14:00", attendees=["a@example.com", "b@example.com"])
    body = mock_gws.call_args_list[0].kwargs["body"]
    assert body["attendees"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]


def test_add_event_rejects_end_before_start():
    with pytest.raises(ValueError):
        add_event("Call", "2026-11-02T14:00", end="2026-11-02T13:00")


@patch("pa_google.calendar.run_gws")
def test_update_event_patches_only_given_fields(mock_gws):
    mock_gws.side_effect = [{}, _raw(summary="Dentist (moved)")]
    update_event("ev1", calendar="Family", title="Dentist (moved)", start="2026-11-03T10:00")
    patch_call = mock_gws.call_args_list[0]
    assert patch_call.args[:3] == ("calendar", "events", "patch")
    assert patch_call.args[3] == {"calendarId": "fam@group", "eventId": "ev1"}
    body = patch_call.kwargs["body"]
    assert body["summary"] == "Dentist (moved)"
    assert body["start"]["dateTime"] == "2026-11-03T10:00:00"
    assert "end" not in body and "location" not in body


@patch("pa_google.calendar.run_gws")
def test_delete_event(mock_gws):
    mock_gws.return_value = None
    delete_event("ev1", calendar="Family")
    assert mock_gws.call_args.args == ("calendar", "events", "delete",
                                       {"calendarId": "fam@group", "eventId": "ev1"})


def test_calendar_module_has_no_naive_utc_suffix():
    # Regression: local times used to be sent with a bare "Z", shifting by the UTC offset.
    import inspect
    assert '+ "Z"' not in inspect.getsource(calendar)
