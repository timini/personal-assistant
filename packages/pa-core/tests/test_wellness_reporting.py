"""Wellness data must make it into the reports, not just exist in helpers."""
from unittest.mock import patch

from pa_core.briefing import (
    _focus_section,
    _gratitude_section,
    _habits_section,
    _health_section,
    _wellness_trend_section,
    _wins_section,
)


def _event(date, category, action, summary, details=None):
    return {
        "date": date,
        "category": category,
        "action": action,
        "summary": summary,
        "details": details or {},
    }


def test_health_section_reports_recovery_and_stress_without_zeros():
    lines = _health_section({
        "ok": True,
        "sleep_hours": 7.9,
        "sleep_quality": "GOOD",
        "resting_hr": 55,
        "hrv": None,
        "avg_stress": 33,
        "max_stress": 99,
        "body_battery_high": 83,
        "body_battery_low": 23,
        "steps": 8123,
    })
    text = "\n".join(lines)
    assert "## Health" in text
    assert "7.9h" in text and "GOOD" in text
    assert "55 bpm" in text
    assert "33 average" in text and "99 max" in text
    assert "23-83" in text
    assert "HRV: 0" not in text


def test_health_section_says_when_source_is_unavailable():
    assert "unavailable" in "\n".join(_health_section({"ok": False})).lower()


def test_wellness_trend_normalises_real_mixed_answers():
    events = [
        _event("2026-08-22", "wellness", "check_in", "", {"mood": "okay", "energy": "2 - Rough"}),
        _event("2026-08-23", "wellness", "check_in", "", {"mood": "4", "energy": "3"}),
        _event("2026-08-24", "wellness", "check_in", "", {"mood": "great", "energy": "4"}),
    ]
    text = "\n".join(_wellness_trend_section(events))
    assert "Mood" in text and "3 -> 4 -> 5" in text
    assert "Energy" in text and "2 -> 3 -> 4" in text
    assert "improving" in text


def test_habit_report_uses_cadence_aware_streak_and_completion_rate():
    history = [
        _event("2026-08-05", "habit", "completed", "Deep clean"),
        _event("2026-08-12", "habit", "completed", "Deep clean"),
        _event("2026-08-19", "habit", "completed", "Deep clean"),
    ]
    config = {"habits": [{"name": "Deep clean", "cadence": "weekly", "target": 1}]}
    with patch("pa_core.briefing.get_user_config", return_value=config):
        text = "\n".join(_habits_section([], "2026-08-24", history=history))
    assert "3 weeks" in text
    assert "3 of the last 5 weeks" in text


def test_gratitude_report_can_surface_recent_entries_with_dates():
    history = [
        _event("2026-08-22", "wellness", "gratitude", "A quiet walk"),
        _event("2026-08-24", "wellness", "gratitude", "Family dinner"),
    ]
    text = "\n".join(_gratitude_section(history))
    assert "2026-08-22" in text and "A quiet walk" in text
    assert "2026-08-24" in text and "Family dinner" in text


def test_explicit_day_plan_replaces_the_generic_backlog_focus():
    events = [
        _event(
            "2026-08-24",
            "task",
            "planned",
            "Conference talk preparation",
        )
    ]
    with patch("pa_notion.tasks.list_tasks") as list_tasks:
        text = "\n".join(_focus_section(events))
    assert "Conference talk preparation" in text
    assert "Chosen plan" in text
    list_tasks.assert_not_called()


def test_wins_section_collapses_duplicate_sync_events():
    event = _event("2026-08-24", "task", "completed", "Completed starter task")
    text = "\n".join(_wins_section([event, dict(event), dict(event)]))
    assert text.count("Completed starter task") == 1


def test_briefings_do_not_sync_retired_google_tasks():
    import inspect

    from pa_core import briefing
    assert "sync_google_tasks" not in inspect.getsource(briefing)


# --- Logged activities in the daily surfaces ---------------------------------
# A run is the most concrete thing that happened to the user's body that day. It
# belongs in the briefing and the morning message, not just in the raw dict.


def _run(**over):
    base = {
        "name": "Morning Run", "type": "running",
        "start": "2026-09-13 11:21:35", "distance_km": 10.01,
        "duration_min": 60.8, "avg_hr": 156, "max_hr": 176,
        "calories": 804, "vo2max": 44, "intensity_minutes": 60, "is_pr": True,
    }
    base.update(over)
    return base


def test_briefing_health_section_lists_activities():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "sleep_hours": 8.3, "activities": [_run()]}))
    assert "Morning Run" in out
    assert "10.01 km" in out
    assert "60.8 min" in out
    assert "156 bpm" in out


def test_briefing_flags_a_personal_record():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "activities": [_run()]}))
    assert "PR" in out


def test_briefing_handles_a_session_with_no_distance():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "activities": [
        _run(name="Strength", type="strength_training", distance_km=None,
             duration_min=30.0, is_pr=False, avg_hr=None)
    ]}))
    assert "Strength" in out
    assert "30.0 min" in out
    assert "None" not in out


def test_briefing_omits_the_activity_line_when_there_are_none():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "sleep_hours": 8.0, "activities": []}))
    assert "Activity" not in out


def test_morning_prompt_mentions_a_logged_run():
    from pa_core.prompts import build_morning_prompt
    out = build_morning_prompt([], [], health={"ok": True, "sleep_hours": 8.3, "activities": [_run()]})
    assert "10.01 km" in out
    assert "running" in out.lower()


# --- Proactive HR-alert review -----------------------------------------------
# An alert with no recorded context is a question owed to the user; once
# they answer it is logged and never asked again.


def _alert(time="21:30", bpm=114, date="2026-09-13"):
    return {"ts": 1, "date": date, "time": time, "bpm": bpm, "threshold": 100}


def test_unlabelled_alerts_are_the_ones_without_a_logged_context():
    from pa_core.context import unlabelled_hr_alerts
    alerts = [_alert("21:30"), _alert("21:44"), _alert("21:55")]
    logged = [{"category": "wellness", "action": "hr_context",
               "details": {"date": "2026-09-13", "time": "21:44"}}]
    got = unlabelled_hr_alerts(alerts, logged)
    assert [a["time"] for a in got] == ["21:30", "21:55"]


def test_an_alert_answered_on_another_day_does_not_silence_todays():
    from pa_core.context import unlabelled_hr_alerts
    alerts = [_alert("21:30", date="2026-09-14")]
    logged = [{"category": "wellness", "action": "hr_context",
               "details": {"date": "2026-09-13", "time": "21:30"}}]
    assert len(unlabelled_hr_alerts(alerts, logged)) == 1


def test_unrelated_log_events_do_not_silence_alerts():
    from pa_core.context import unlabelled_hr_alerts
    alerts = [_alert("21:30")]
    logged = [{"category": "task", "action": "created", "details": {}},
              {"category": "wellness", "action": "something_else",
               "details": {"date": "2026-09-13", "time": "21:30"}}]
    assert len(unlabelled_hr_alerts(alerts, logged)) == 1


def test_no_alerts_is_an_empty_list():
    from pa_core.context import unlabelled_hr_alerts
    assert unlabelled_hr_alerts([], []) == []


def test_briefing_asks_about_unlabelled_alerts():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "sleep_hours": 8.0,
                                     "abnormal_hr": [_alert("21:30", 114)]}))
    assert "21:30" in out
    assert "114" in out


def test_briefing_says_nothing_when_there_were_no_alerts():
    from pa_core.briefing import _health_section
    out = "\n".join(_health_section({"ok": True, "sleep_hours": 8.0, "abnormal_hr": []}))
    assert "heart" not in out.lower()


# --- Weekly running line in the briefing -------------------------------------


def test_briefing_reports_the_weekly_running_total():
    from pa_core.briefing import _running_week_line
    line = _running_week_line({"runs": 3, "distance_km": 16.4, "duration_min": 98.0, "avg_hr": 152})
    assert "16.4 km" in line
    assert "3 runs" in line
    assert "152" in line


def test_briefing_running_line_without_heart_rate():
    from pa_core.briefing import _running_week_line
    line = _running_week_line({"runs": 1, "distance_km": 5.0, "duration_min": 30.0, "avg_hr": None})
    assert "5.0 km" in line
    assert "bpm" not in line


def test_briefing_running_line_is_empty_when_no_runs():
    from pa_core.briefing import _running_week_line
    assert _running_week_line({"runs": 0, "distance_km": 0.0, "duration_min": 0.0, "avg_hr": None}) == ""
