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


def test_alerts_lists_only_unexplained(capsys):
    alerts = [{"date": "2026-10-20", "time": "03:10", "bpm": 130, "threshold": 120},
              {"date": "2026-10-20", "time": "14:00", "bpm": 125, "threshold": 120}]
    day = {**EMPTY, "date": "2026-10-20", "ok": True, "abnormal_hr": alerts}
    logged = [{"category": "wellness", "action": "hr_context",
               "details": {"date": "2026-10-20", "time": "14:00"}}]
    with patch("pa_health.cli.get_health", return_value=day), \
         patch("pa_health.cli._today", return_value="2026-10-20"), \
         patch("pa_core.daily_log.get_events", return_value=logged):
        out = _run(["alerts", "--days", "1"], capsys)
    assert "03:10" in out and "130 bpm" in out
    assert "14:00" not in out


def test_alerts_json_and_empty(capsys):
    with patch("pa_health.cli.get_health", return_value={**EMPTY, "date": "d"}), \
         patch("pa_health.cli._today", return_value="2026-10-20"), \
         patch("pa_core.daily_log.get_events", return_value=[]):
        out = _run(["alerts", "--json"], capsys)
    assert json.loads(out) == []


class TestWorkout:
    def test_log_parses_exercises_and_prints_the_session(self, capsys):
        with patch("pa_core.training._today", return_value="2026-10-21"), \
             patch("pa_core.daily_log.log_event"), patch("pa_core.daily_log.get_events", return_value=[]):
            out = _run(["workout", "log", "--type", "strength", "--exercise", "bench press=3x10@50",
                        "--exercise", "curl=3x10@10/side", "--rpe", "7"], capsys)
        assert "Logged 2026-10-21-1 strength (done)" in out
        assert "bench press: 3 sets, 10x50.0kg" in out
        assert "curl: 3 sets, 10x10.0kg per side" in out

    def test_bad_exercise_is_a_clear_error(self, capsys):
        with patch("pa_core.training._today", return_value="2026-10-21"):
            try:
                _run(["workout", "log", "--type", "strength", "--exercise", "bench"], capsys)
            except SystemExit as exc:
                assert exc.code == 1
        assert "bench press=3x10@50" in capsys.readouterr().err

    def test_plan_then_update_missed(self, capsys):
        out = _run(["workout", "plan", "--date", "2026-10-20", "--time", "19:00", "--type", "run"], capsys)
        assert "Planned 2026-10-20-1" in out
        with patch("pa_core.training._today", return_value="2026-10-21"):
            out = _run(["workout", "update", "2026-10-20-1", "--status", "missed"], capsys)
        assert "2026-10-20-1 run (missed)" in out

    def test_sync_reads_garmin_range(self, capsys):
        acts = [{"id": 5, "name": "Run", "type": "running", "start": "2026-10-19 07:00:00",
                 "distance_km": 5.0, "duration_min": 28.0}]
        with patch("pa_health.cli.get_activities_range", return_value=acts) as m, \
             patch("pa_health.cli._today", return_value="2026-10-21"):
            out = _run(["workout", "sync", "--days", "7"], capsys)
        m.assert_called_once_with("2026-10-15", "2026-10-21")
        assert "Garmin sync 2026-10-15 to 2026-10-21: 1 added, 0 merged, 0 already logged" in out

    def test_history_for_one_exercise(self, capsys):
        from pa_core import training
        with patch("pa_core.daily_log.log_event"), patch("pa_core.daily_log.get_events", return_value=[]):
            training.log("strength", date="2026-10-21", today="2026-10-21",
                         exercises=[training.parse_exercise("bench press=3x10@50")])
        out = _run(["workout", "history", "--exercise", "bench"], capsys)
        assert "2026-10-21  3 sets  top 50.0 kg  best 10x50.0kg  volume 1500 kg" in out

    def test_week_json(self, capsys):
        with patch("pa_health.cli._today", return_value="2026-10-21"):
            out = _run(["workout", "week", "--json"], capsys)
        assert json.loads(out)["sessions"] == 0
