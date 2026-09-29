"""Health in the session context.

The rule that matters: a health source that is down, unauthenticated or
returning nonsense must never break a briefing. It degrades to missing data.
"""
from unittest.mock import patch

from pa_core.context import _fetch_health


def test_health_is_returned_when_the_source_works():
    fake = {"date": "2026-08-24", "sleep_hours": 7.2, "resting_hr": 51, "ok": True}
    with patch("pa_health.client.get_health", return_value=fake):
        assert _fetch_health("2026-08-24")["sleep_hours"] == 7.2


def test_source_raising_degrades_to_missing_rather_than_propagating():
    with patch("pa_health.client.get_health", side_effect=RuntimeError("garmin blocked login")):
        got = _fetch_health("2026-08-24")
        assert got["ok"] is False
        assert got["date"] == "2026-08-24"


def test_package_not_installed_degrades_too():
    with patch.dict("sys.modules", {"pa_health.client": None}):
        got = _fetch_health("2026-08-24")
        assert got["ok"] is False
