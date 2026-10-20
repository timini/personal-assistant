"""Health data normalisation.

Consumers depend on the shape, never on Garmin. These tests use recorded
fixtures shaped like real Garmin responses so they never touch the network,
and they pin the behaviour that matters most: a broken or partial source
degrades to missing data rather than raising, because a briefing must never
fail because a watch did not sync.
"""
import pytest

from pa_health.client import EMPTY, normalise


def test_shape_is_stable_even_with_no_data():
    """Every key exists whatever happens, so consumers never KeyError."""
    expected = {
        "date", "sleep_hours", "sleep_quality", "resting_hr",
        "hrv", "avg_stress", "max_stress", "body_battery_high",
        "body_battery_low", "steps", "activities", "abnormal_hr",
        "source", "ok",
    }
    assert set(EMPTY) == expected


def test_sleep_seconds_convert_to_hours():
    got = normalise("2026-08-24", sleep={"dailySleepDTO": {"sleepTimeSeconds": 27000}})
    assert got["sleep_hours"] == 7.5


def test_sleep_quality_is_carried_through():
    got = normalise("2026-08-24", sleep={
        "dailySleepDTO": {"sleepTimeSeconds": 25200, "sleepScores": {"overall": {"qualifierKey": "GOOD"}}}
    })
    assert got["sleep_quality"] == "GOOD"


def test_resting_heart_rate_is_read_from_the_nested_shape():
    got = normalise("2026-08-24", rhr={
        "allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 52}]}}
    })
    assert got["resting_hr"] == 52


def test_hrv_uses_the_weekly_average_not_the_nightly_value():
    """Garmin's own guidance is that the 7-day average is the meaningful figure;
    a single night is too noisy to coach from."""
    got = normalise("2026-08-24", hrv={"hrvSummary": {"weeklyAvg": 42, "lastNightAvg": 61}})
    assert got["hrv"] == 42


def test_stress_summaries_are_read_from_all_day_stress():
    got = normalise(
        "2026-08-24",
        stress={"avgStressLevel": 33, "maxStressLevel": 99},
    )
    assert got["avg_stress"] == 33
    assert got["max_stress"] == 99


def test_missing_or_malformed_stress_is_safe():
    for stress in (None, {}, [], "nonsense", {"avgStressLevel": None}):
        got = normalise("2026-08-24", stress=stress)
        assert got["avg_stress"] is None
        assert got["max_stress"] is None


def test_body_battery_carries_both_ends_of_the_day():
    got = normalise("2026-08-24", battery=[{"charged": 78, "drained": 62}])
    assert got["body_battery_high"] == 78
    assert got["body_battery_low"] == 62


def test_partial_data_fills_what_it_can_and_leaves_the_rest_none():
    got = normalise("2026-08-24", sleep={"dailySleepDTO": {"sleepTimeSeconds": 21600}})
    assert got["sleep_hours"] == 6.0
    assert got["resting_hr"] is None
    assert got["hrv"] is None
    assert got["ok"] is True  # we got *something*


def test_no_data_at_all_is_not_ok():
    got = normalise("2026-08-24")
    assert got["ok"] is False
    assert got["sleep_hours"] is None


def test_malformed_payloads_do_not_raise():
    """A watch that half-synced returns odd shapes. Never crash a briefing."""
    for bad in (None, {}, [], {"dailySleepDTO": None}, {"dailySleepDTO": {}}, "nonsense"):
        got = normalise("2026-08-24", sleep=bad, rhr=bad, hrv=bad, battery=bad)
        assert got["date"] == "2026-08-24"
        assert got["sleep_hours"] is None


def test_date_is_always_echoed_back():
    assert normalise("2026-01-01")["date"] == "2026-01-01"


@pytest.mark.parametrize("seconds,hours", [(0, None), (3600, 1.0), (28800, 8.0), (29160, 8.1)])
def test_sleep_rounding_and_zero_handling(seconds, hours):
    """Zero seconds means no sleep recorded, which is missing data, not 0 hours."""
    got = normalise("2026-08-24", sleep={"dailySleepDTO": {"sleepTimeSeconds": seconds}})
    assert got["sleep_hours"] == hours


def test_context_fallback_shape_matches_the_contract():
    """context.py duplicates the empty shape so its fallback does not depend on
    this package. If a key is added here, that copy must be updated too — this
    test is what catches the drift."""
    from pa_core.context import _fetch_health
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
        "sys.modules", {"pa_health.client": None}
    ):
        fallback = _fetch_health("2026-08-24")
    # context.py adds `running_week` on top: a 7-day rolling total is a context
    # concern, not one day of health data, so it is deliberately not in EMPTY.
    extra = {"running_week"}
    assert set(EMPTY) <= set(fallback), "context.py fallback is missing keys from EMPTY"
    assert set(fallback) - set(EMPTY) == extra, (
        "context.py fallback has keys beyond EMPTY that this test does not know about"
    )


# --- Logged activities -------------------------------------------------------
# Garmin records runs, rides and gym sessions separately from the daily
# wellness roll-up. Steps alone cannot tell a 10k from a day of walking, so the
# coaching layer needs the sessions themselves.


def test_activities_key_is_part_of_the_contract():
    """A day with no sessions is an empty list, never None, so callers can
    iterate without a guard."""
    assert EMPTY["activities"] == []


def test_activity_is_normalised_to_the_useful_fields():
    raw = [{
        "activityId": 24346765388,
        "activityName": "Morning Run",
        "startTimeLocal": "2026-09-13 11:21:35",
        "activityType": {"typeKey": "running"},
        "distance": 10013.0498046875,
        "duration": 3649.45703125,
        "averageHR": 156.0,
        "maxHR": 176.0,
        "calories": 804.0,
        "isPR": True,
        "vO2MaxValue": 44.0,
        "moderateIntensityMinutes": 5,
        "vigorousIntensityMinutes": 55,
    }]
    got = normalise("2026-09-13", activities=raw)["activities"]
    assert len(got) == 1
    a = got[0]
    assert a["name"] == "Morning Run"
    assert a["type"] == "running"
    assert a["start"] == "2026-09-13 11:21:35"
    assert a["distance_km"] == 10.01       # metres to km, 2dp
    assert a["duration_min"] == 60.8       # seconds to minutes, 1dp
    assert a["avg_hr"] == 156
    assert a["max_hr"] == 176
    assert a["calories"] == 804
    assert a["is_pr"] is True
    assert a["vo2max"] == 44
    assert a["intensity_minutes"] == 60    # moderate + vigorous


def test_activities_without_distance_still_normalise():
    """Strength and yoga sessions carry no distance. They are still sessions."""
    got = normalise("2026-09-13", activities=[{
        "activityName": "Strength",
        "activityType": {"typeKey": "strength_training"},
        "startTimeLocal": "2026-09-13 07:00:00",
        "duration": 1800.0,
    }])["activities"]
    assert got[0]["distance_km"] is None
    assert got[0]["duration_min"] == 30.0
    assert got[0]["type"] == "strength_training"


def test_malformed_activities_degrade_to_empty_list():
    """Half-synced or unexpected shapes must not break a briefing."""
    for bad in (None, {}, "nonsense", 42, [None], ["nonsense"]):
        assert normalise("2026-09-13", activities=bad)["activities"] == []


def test_activities_alone_are_enough_to_mark_the_day_ok():
    """A logged run is real data even if the wellness roll-up has not synced."""
    got = normalise("2026-09-13", activities=[{
        "activityName": "Run", "activityType": {"typeKey": "running"},
        "duration": 600.0,
    }])
    assert got["ok"] is True


# --- Abnormal heart rate alerts ----------------------------------------------
# Garmin records its own high-HR alerts in abnormalHRValuesArray on the daily
# heart-rate payload. They are surfaced and asked about because the calendar
# often cannot explain them.


def test_abnormal_hr_is_part_of_the_contract():
    assert EMPTY["abnormal_hr"] == []


def test_abnormal_hr_events_are_normalised_with_local_time():
    got = normalise("2026-09-13", heart_rates={
        "abnormalHrThresholdValue": 100,
        "abnormalHRValuesArray": [[1789305660000, 110], [1789314300000, 103]],
    })["abnormal_hr"]
    assert len(got) == 2
    assert got[0]["bpm"] == 110
    assert got[0]["time"] == "14:21"      # Europe/London, not UTC
    assert got[0]["date"] == "2026-09-13"
    assert got[1]["time"] == "16:45"
    assert got[0]["threshold"] == 100


def test_abnormal_hr_events_are_sorted_by_time():
    got = normalise("2026-09-13", heart_rates={
        "abnormalHRValuesArray": [[1789314300000, 103], [1789305660000, 110]],
    })["abnormal_hr"]
    assert [e["time"] for e in got] == ["14:21", "16:45"]


def test_no_abnormal_hr_is_an_empty_list_not_none():
    assert normalise("2026-09-13", heart_rates={"abnormalHRValuesArray": []})["abnormal_hr"] == []
    assert normalise("2026-09-13", heart_rates={})["abnormal_hr"] == []


def test_malformed_abnormal_hr_degrades_to_empty_list():
    for bad in (None, [], "nonsense", {"abnormalHRValuesArray": "nope"},
                {"abnormalHRValuesArray": [None, "x", [1]]}):
        assert normalise("2026-09-13", heart_rates=bad)["abnormal_hr"] == []


def test_an_alert_alone_marks_the_day_ok():
    """An alert is real data even when nothing else has synced."""
    got = normalise("2026-09-13", heart_rates={"abnormalHRValuesArray": [[1789305660000, 110]]})
    assert got["ok"] is True


# --- Weekly running summary --------------------------------------------------
# Weekly volume matters more than any single run, so the check-in reports it.


def _run(km=5.0, mins=30.0, hr=150, typ="running"):
    return {"type": typ, "distance_km": km, "duration_min": mins, "avg_hr": hr}


def test_weekly_summary_totals_distance_and_time():
    from pa_health.client import weekly_summary
    got = weekly_summary([_run(5.0, 30.0, 150), _run(10.0, 60.0, 156)])
    assert got["runs"] == 2
    assert got["distance_km"] == 15.0
    assert got["duration_min"] == 90.0


def test_weekly_summary_weights_average_hr_by_duration():
    """A 60-minute run should count twice as much as a 30-minute one."""
    from pa_health.client import weekly_summary
    got = weekly_summary([_run(5.0, 30.0, 180), _run(10.0, 60.0, 150)])
    assert got["avg_hr"] == 160          # (180*30 + 150*60) / 90


def test_weekly_summary_ignores_non_running_activities():
    from pa_health.client import weekly_summary
    got = weekly_summary([_run(5.0, 30.0, 150), _run(0, 60.0, 120, typ="strength_training")])
    assert got["runs"] == 1
    assert got["distance_km"] == 5.0


def test_weekly_summary_handles_runs_without_heart_rate():
    """A manually logged run has no HR. It still counts toward distance."""
    from pa_health.client import weekly_summary
    got = weekly_summary([_run(5.0, 30.0, None), _run(5.0, 30.0, 150)])
    assert got["runs"] == 2
    assert got["distance_km"] == 10.0
    assert got["avg_hr"] == 150


def test_weekly_summary_of_nothing_is_zeroes_not_none():
    from pa_health.client import weekly_summary
    got = weekly_summary([])
    assert got == {"runs": 0, "distance_km": 0.0, "duration_min": 0.0, "avg_hr": None}


def test_weekly_summary_survives_junk():
    from pa_health.client import weekly_summary
    for bad in (None, "nonsense", [None], [{"type": "running"}]):
        got = weekly_summary(bad)
        assert got["runs"] in (0, 1) and got["distance_km"] == 0.0
