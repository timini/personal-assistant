"""Tests for get_now() — must expose an epoch for date filtering."""

from pa_core.config import get_now


def test_get_now_includes_epoch():
    now = get_now()
    assert "epoch" in now
    assert isinstance(now["epoch"], int)
    # sane recent epoch (after 2023-11)
    assert now["epoch"] > 1_700_000_000


def test_get_now_still_has_core_fields():
    now = get_now()
    for key in ("date", "day", "time", "timezone", "period", "display"):
        assert key in now
