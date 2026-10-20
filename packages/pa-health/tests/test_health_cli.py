"""Tests for the pa-health CLI."""

import json
from unittest.mock import patch

from pa_health import cli
from pa_health.client import EMPTY


def _run(argv, capsys):
    with patch.object(cli.sys, "argv", ["pa-health", *argv]):
        cli.main()
    return capsys.readouterr().out


def test_day_json_passes_date(capsys):
    day = {**EMPTY, "date": "2026-10-19", "ok": True, "sleep_hours": 7.5}
    with patch("pa_health.cli.get_health", return_value=day) as m:
        out = _run(["day", "--date", "2026-10-19", "--json"], capsys)
    m.assert_called_once_with("2026-10-19")
    assert json.loads(out)["sleep_hours"] == 7.5


def test_day_text_says_when_no_data(capsys):
    with patch("pa_health.cli.get_health", return_value={**EMPTY, "date": "2026-10-19"}):
        out = _run(["day"], capsys)
    assert "No health data" in out


def test_day_text_lists_readings_and_activities(capsys):
    day = {**EMPTY, "date": "2026-10-19", "ok": True, "sleep_hours": 7.5, "resting_hr": 50,
           "activities": [{"name": "Morning run", "type": "running", "distance_km": 5.0,
                           "duration_min": 28.0, "avg_hr": 150}]}
    with patch("pa_health.cli.get_health", return_value=day):
        out = _run(["day"], capsys)
    assert "Sleep: 7.5 h" in out
    assert "Morning run" in out


def test_activities_range_from_days(capsys):
    with patch("pa_health.cli.get_activities_range", return_value=[]) as m, \
         patch("pa_health.cli._today", return_value="2026-10-20"):
        _run(["activities", "--days", "7", "--json"], capsys)
    m.assert_called_once_with("2026-10-14", "2026-10-20")


def test_activities_explicit_range_and_summary(capsys):
    acts = [{"name": "Run", "type": "running", "start": "2026-10-15 07:00", "distance_km": 5.0,
             "duration_min": 30.0, "avg_hr": 150}]
    with patch("pa_health.cli.get_activities_range", return_value=acts) as m:
        out = _run(["activities", "--from", "2026-10-01", "--to", "2026-10-15"], capsys)
    m.assert_called_once_with("2026-10-01", "2026-10-15")
    assert "Run" in out
    assert "1 activities" in out
