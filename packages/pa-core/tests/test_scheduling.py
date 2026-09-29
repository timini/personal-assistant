"""Generating LaunchAgents from user.yaml.

Config is the source of truth; plists are generated. Hand-edited plists drift
from config, and on 2026-08-24 two scheduled jobs failed silently — one on a
wrong uv path, one because it ran against a dev branch. Both are addressed by
generating the plist rather than writing it by hand.
"""
from pa_core.scheduling import build_plist, parse_time


def test_parse_time_splits_hh_mm():
    assert parse_time("06:30") == (6, 30)
    assert parse_time("21:00") == (21, 0)


def test_parse_time_rejects_nonsense_rather_than_scheduling_at_midnight():
    """A typo'd time silently becoming 00:00 is worse than a loud failure."""
    for bad in ("", "half six", "25:00", "06:99", None):
        try:
            parse_time(bad)
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"{bad!r} should not have parsed")


def test_plist_uses_an_absolute_uv_path():
    """The exact bug that broke the weekly report: /opt/homebrew/bin/uv did not exist."""
    xml = build_plist("morning", "06:30", uv="/Users/x/.local/bin/uv", repo="/repo")
    assert "/Users/x/.local/bin/uv" in xml
    assert "/opt/homebrew/bin/uv" not in xml


def test_plist_encodes_the_configured_time():
    xml = build_plist("morning", "06:30", uv="/uv", repo="/repo")
    assert "<integer>6</integer>" in xml
    assert "<integer>30</integer>" in xml


def test_plist_is_wellformed_and_labelled_per_slot():
    for slot in ("morning", "evening"):
        xml = build_plist(slot, "07:00", uv="/uv", repo="/repo")
        assert xml.lstrip().startswith("<?xml")
        assert f"com.pa.wellness-{slot}" in xml
        assert f"--{slot}" in xml


def test_plist_does_not_run_at_load():
    """Loading the agent must not fire an unexpected 06:30 message at 3pm."""
    assert "<key>RunAtLoad</key>\n    <false/>" in build_plist("morning", "06:30", uv="/uv", repo="/repo")
