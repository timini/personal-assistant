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
        "hrv", "body_battery_high", "body_battery_low", "steps", "source", "ok",
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
    assert set(fallback) == set(EMPTY), "context.py fallback shape has drifted from EMPTY"
