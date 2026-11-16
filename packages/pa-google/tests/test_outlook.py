"""Tests for pa_google.outlook — reading the work calendar from (Legacy) Outlook via AppleScript."""

from unittest.mock import MagicMock, patch

import pytest

from pa_google import outlook

US = "\x1f"
# subject, sY,sMo,sD,sH,sMi, eY,eMo,eD,eH,eMi, location, all_day
SAMPLE = (
    f"Standup{US}2026{US}6{US}17{US}9{US}0{US}2026{US}6{US}17{US}9{US}30{US}{US}false\n"
    f"PDR Robert / Tim{US}2026{US}6{US}17{US}14{US}30{US}2026{US}6{US}17{US}15{US}15{US}Microsoft Teams Meeting{US}false\n"
)


def test_parse_basic():
    evs = outlook._parse_outlook_output(SAMPLE)
    assert len(evs) == 2
    assert evs[0]["summary"] == "Standup"
    assert evs[0]["start"] == "2026-06-17T09:00:00"
    assert evs[0]["end"] == "2026-06-17T09:30:00"
    assert evs[0]["location"] == ""
    assert evs[0]["all_day"] is False
    assert evs[1]["summary"] == "PDR Robert / Tim"
    assert evs[1]["start"] == "2026-06-17T14:30:00"
    assert evs[1]["location"] == "Microsoft Teams Meeting"
    assert evs[1]["key"] == "PDR Robert / Tim|2026-06-17T14:30:00"


def test_parse_zero_pads_and_handles_missing_location():
    raw = f"Focus{US}2026{US}6{US}9{US}9{US}5{US}2026{US}6{US}9{US}9{US}35{US}missing value{US}false\n"
    evs = outlook._parse_outlook_output(raw)
    assert evs[0]["start"] == "2026-06-09T09:05:00"
    assert evs[0]["location"] == ""  # "missing value" normalised to empty


def test_parse_skips_blank_and_malformed():
    raw = f"\n\nonlyonefield\nGood{US}2026{US}6{US}17{US}9{US}0{US}2026{US}6{US}17{US}9{US}30{US}{US}false\n"
    evs = outlook._parse_outlook_output(raw)
    assert len(evs) == 1
    assert evs[0]["summary"] == "Good"


def test_get_outlook_events_runs_osascript_and_parses():
    fake = MagicMock(returncode=0, stdout=SAMPLE, stderr="")
    with patch("pa_google.outlook.run_cli", return_value=fake) as m:
        evs = outlook.get_outlook_events(days=7)
    assert len(evs) == 2
    cmd = m.call_args[0][0]
    assert cmd[0] == "osascript"
    assert "7" in " ".join(cmd)  # day window threaded into the script


def test_get_outlook_events_raises_when_not_running():
    fake = MagicMock(returncode=0, stdout="OUTLOOK_NOT_RUNNING", stderr="")
    with patch("pa_google.outlook.run_cli", return_value=fake):
        with pytest.raises(outlook.OutlookError):
            outlook.get_outlook_events()


def test_get_outlook_events_raises_on_osascript_failure():
    fake = MagicMock(returncode=1, stdout="", stderr="boom")
    with patch("pa_google.outlook.run_cli", return_value=fake):
        with pytest.raises(outlook.OutlookError):
            outlook.get_outlook_events()
