"""Structured training log: sessions, plans, Garmin sync and progression."""

from unittest.mock import patch

import pytest

from pa_core import training


@pytest.fixture
def habit_events():
    """Capture habit events instead of writing the real daily log."""
    logged = []
    existing = []

    def fake_log(category, action, summary, details=None, **_):
        logged.append({"category": category, "action": action, "summary": summary, "details": details})
        return logged[-1]

    with patch("pa_core.daily_log.log_event", side_effect=fake_log), \
         patch("pa_core.daily_log.get_events", side_effect=lambda date=None: existing + logged):
        yield logged, existing


class TestParseExercise:
    def test_sets_reps_and_weight(self):
        assert training.parse_exercise("Bench press=3x10@50") == {
            "name": "Bench press",
            "sets": [{"reps": 10, "weight_kg": 50.0, "per_side": False}] * 3,
        }

    def test_per_side_and_decimal_weight(self):
        ex = training.parse_exercise("lateral raise = 3x10@7.5kg/side")
        assert ex["name"] == "lateral raise"
        assert ex["sets"] == [{"reps": 10, "weight_kg": 7.5, "per_side": True}] * 3

    def test_sets_that_differ(self):
        ex = training.parse_exercise("bench=12@40,10@45,8@50")
        assert [(s["reps"], s["weight_kg"]) for s in ex["sets"]] == [(12, 40), (10, 45), (8, 50)]

    def test_bodyweight(self):
        assert training.parse_exercise("pull up=3x5")["sets"] == [{"reps": 5, "weight_kg": None, "per_side": False}] * 3

    @pytest.mark.parametrize("bad", ["bench", "bench=", "bench=x12@40", "=3x5"])
    def test_rejects_malformed(self, bad):
        with pytest.raises(ValueError):
            training.parse_exercise(bad)


class TestPlanAndLog:
    def test_plan_without_type_is_closed_by_log(self, habit_events):
        planned = training.plan("2026-01-05", time="12:30")
        assert planned["status"] == "planned" and planned["type"] is None

        done = training.log("strength", date="2026-01-05", today="2026-01-05",
                            exercises=[training.parse_exercise("bench=3x10@50")])
        assert done["id"] == planned["id"]
        assert done["status"] == "done" and done["type"] == "strength" and done["time"] == "12:30"
        assert len(training.sessions()) == 1

    def test_log_does_not_close_a_plan_of_another_type(self, habit_events):
        training.plan("2026-01-05", type="run")
        training.log("strength", date="2026-01-05", today="2026-01-05")
        assert sorted(s["type"] for s in training.sessions()) == ["run", "strength"]

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError):
            training.plan("2026-01-05", type="karate-ish")

    def test_done_today_ticks_the_exercise_habit_once(self, habit_events):
        logged, _ = habit_events
        training.log("strength", date="2026-01-05", today="2026-01-05")
        training.log("run", date="2026-01-05", today="2026-01-05")
        assert [(e["category"], e["action"], e["summary"]) for e in logged] == [("habit", "completed", "Exercise")]

    def test_existing_habit_event_is_respected(self, habit_events):
        logged, existing = habit_events
        existing.append({"category": "habit", "action": "completed", "summary": "Exercise"})
        training.log("walk", date="2026-01-05", today="2026-01-05")
        assert logged == []

    def test_past_session_does_not_touch_the_daily_log(self, habit_events):
        logged, _ = habit_events
        training.log("run", date="2026-01-01", today="2026-01-05")
        assert logged == []

    def test_update_marks_missed_and_adds_exercises(self, habit_events):
        logged, _ = habit_events
        s = training.plan("2026-01-04", type="run")
        assert training.update(s["id"], status="missed", today="2026-01-05")["status"] == "missed"
        g = training.log("strength", date="2026-01-05", today="2026-01-05",
                         exercises=[training.parse_exercise("curl=3x10@10/side")])
        out = training.update(g["id"], exercises=[training.parse_exercise("bench=3x10@50")], rpe=7,
                              feel="good", today="2026-01-05")
        assert [e["name"] for e in out["exercises"]] == ["curl", "bench"]
        assert out["rpe"] == 7 and out["feel"] == "good"
        assert len(logged) == 1

    def test_update_unknown_id(self):
        with pytest.raises(KeyError):
            training.update("nope", status="done")

    def test_unresolved_plans_are_past_plans_only(self):
        training.plan("2026-01-03", type="strength")
        training.plan("2026-01-05", time="18:00")
        assert [s["date"] for s in training.unresolved_plans("2026-01-05")] == ["2026-01-03"]


GARMIN_RUN = {"id": 111, "name": "Morning Run", "type": "running", "start": "2026-01-05 07:10:00",
              "distance_km": 10.0, "duration_min": 55.0, "avg_hr": 150, "max_hr": 172,
              "training_load": 120.5, "aerobic_te": 3.4}


class TestSync:
    def test_creates_done_session_and_is_idempotent(self, habit_events):
        logged, _ = habit_events
        assert training.sync_activities([GARMIN_RUN]) == {"added": 1, "merged": 0, "skipped": 0}
        assert training.sync_activities([GARMIN_RUN]) == {"added": 0, "merged": 0, "skipped": 1}
        (s,) = training.sessions()
        assert (s["type"], s["status"], s["source"], s["garmin_id"]) == ("run", "done", "garmin", 111)
        assert s["date"] == "2026-01-05" and s["time"] == "07:10" and s["distance_km"] == 10.0
        assert logged == []  # backfill never writes habit events

    def test_merges_into_the_users_session(self, habit_events):
        planned = training.plan("2026-01-05", type="run", time="07:00")
        assert training.sync_activities([GARMIN_RUN])["merged"] == 1
        (s,) = training.sessions()
        assert s["id"] == planned["id"] and s["status"] == "done" and s["source"] == "both"
        assert s["avg_hr"] == 150 and s["training_load"] == 120.5

    def test_breathwork_is_not_training(self):
        result = training.sync_activities([{**GARMIN_RUN, "id": 8, "type": "breathwork"},
                                           {**GARMIN_RUN, "id": 9, "type": "meditation"}])
        assert result == {"added": 0, "merged": 0, "skipped": 2}
        assert training.sessions() == []

    def test_unknown_garmin_type_maps_to_other(self):
        training.sync_activities([{**GARMIN_RUN, "id": 9, "type": "pickleball"}])
        assert training.sessions()[0]["type"] == "other"


class TestProgress:
    def test_exercise_history(self, habit_events):
        training.log("strength", date="2026-01-01", today="2026-01-05",
                     exercises=[training.parse_exercise("Bench press=3x10@50")])
        training.log("strength", date="2026-01-05", today="2026-01-05",
                     exercises=[training.parse_exercise("bench press=12@40,10@45,8@50"),
                                training.parse_exercise("curl=3x10@10/side")])
        hist = training.exercise_history("bench")
        assert [h["date"] for h in hist] == ["2026-01-01", "2026-01-05"]
        assert hist[0]["top_weight_kg"] == 50 and hist[0]["volume_kg"] == 1500
        assert hist[1]["top_weight_kg"] == 50 and hist[1]["best_set"] == {"reps": 8, "weight_kg": 50.0, "per_side": False}
        curl = training.exercise_history("curl")[0]
        assert curl["volume_kg"] == 3 * 10 * 10 * 2

    def test_week_summary(self, habit_events):
        training.sync_activities([GARMIN_RUN])
        training.log("strength", date="2026-01-03", today="2026-01-05", duration_min=40)
        training.log("yoga", date="2025-12-20", today="2026-01-05")
        training.plan("2026-01-04", type="climb")
        week = training.week_summary("2026-01-05")
        assert week["sessions"] == 2
        assert week["by_type"] == {"run": 1, "strength": 1}
        assert week["minutes"] == 95.0 and week["km"] == 10.0
        assert week["last_session"]["date"] == "2026-01-05" and week["days_since_last"] == 0
        assert [p["date"] for p in week["unresolved"]] == ["2026-01-04"]

    def test_brief_line(self, habit_events):
        assert training.brief_line("2026-01-05") == (
            "Exercise: nothing logged in the last 7 days. Load the personal-trainer skill to plan a session.")
        training.log("strength", date="2026-01-03", today="2026-01-05")
        training.plan("2026-01-04", type="run")
        training.plan("2026-01-05", time="12:30")
        line = training.brief_line("2026-01-05")
        assert line.startswith("Exercise: last session 2026-01-03 (strength), 1 in the last 7 days.")
        assert "Planned today: 12:30 (activity not chosen)." in line
        assert "Unresolved plans: 2026-01-04 run; ask what happened." in line


def test_store_is_isolated_in_tests(tmp_path):
    assert str(training._file()).startswith(str(tmp_path))
