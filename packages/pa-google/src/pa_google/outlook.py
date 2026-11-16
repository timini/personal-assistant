"""Read the work calendar from the (Legacy) Microsoft Outlook desktop app via AppleScript.

Why AppleScript and not the API: the work account lives in Microsoft 365 (Genomics
England). New Outlook for Mac exposes 0 events to AppleScript and encrypts its tokens
at rest, and the OWA REST API rejects cookie auth (401) — so the clean route is the
*Legacy* Outlook app, which fully exposes calendar events to AppleScript locally (no
credentials, no browser). Requires Outlook running in Legacy mode.

The user has 60+ calendars (their own Exchange calendar plus many empty colleague
calendars synced locally); we pick the work calendar by content — the calendar with
the most events in the window — rather than a brittle index.

AppleScript date formatting is fiddly, so the script emits raw date *components* and
Python assembles the ISO strings (`_parse_outlook_output`).

KNOWN LIMITATION — RECURRING EVENTS ARE DROPPED (TODO, found 24 Jun 2026):
The query `every calendar event whose start time ≥ startDate and ≤ endDate` filters on
the *master* event's start time, which for a recurring series is the FIRST occurrence
(e.g. a daily 09:30 standup whose series began 24 Feb). That date is before the sync
window, so the whole series — and every occurrence inside the window — is excluded.
Result: ALL recurring meetings (daily huddles, weekly 1:1s, refinements) are missing
from the synced "Day Job" calendar; only one-off events come through.
Fix needed: detect recurring events (`is recurring of e`) and expand their occurrences
into the window. Outlook-for-Mac exposes `recurrence of e` as an AppleScript *record*
(not an object), so its rule fields (type/interval/weekday/end) must be read by their
record labels and the occurrences projected in Python using the master's time-of-day.
"""

from __future__ import annotations

from pa_core.cli_runner import run_cli

OUTLOOK_NOT_RUNNING = "OUTLOOK_NOT_RUNNING"
_US = "\x1f"  # field delimiter (unit separator) — safe against subjects/locations
_DEFAULT_TIMEOUT = 120
# field layout per line emitted by the AppleScript
_NFIELDS = 13


class OutlookError(RuntimeError):
    """Raised when Outlook can't be read (not running, Legacy mode off, or osascript error)."""


def _iso(y: str, mo: str, d: str, h: str, mi: str) -> str:
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}T{int(h):02d}:{int(mi):02d}:00"


def _parse_outlook_output(raw: str) -> list[dict]:
    """Parse the delimited osascript output (date components) into event dicts.

    Each line (US-delimited, 13 fields):
      subject, sY, sMo, sD, sH, sMi, eY, eMo, eD, eH, eMi, location, all_day
    Blank/short/garbled lines are skipped.
    """
    events: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        p = line.split(_US)
        if len(p) < _NFIELDS:
            continue
        subject, sY, sMo, sD, sH, sMi, eY, eMo, eD, eH, eMi, loc, all_day = p[:_NFIELDS]
        try:
            start = _iso(sY, sMo, sD, sH, sMi)
            end = _iso(eY, eMo, eD, eH, eMi)
        except (ValueError, TypeError):
            continue
        events.append({
            "key": f"{subject}|{start}",
            "summary": subject,
            "start": start,
            "end": end,
            "location": "" if loc == "missing value" else loc,
            "all_day": all_day.strip().lower() == "true",
        })
    return events


def _build_applescript(days: int) -> str:
    """AppleScript: pick the busiest calendar in the window and emit its events as components."""
    return f'''tell application "System Events"
	if not (exists (processes whose name is "Microsoft Outlook")) then return "{OUTLOOK_NOT_RUNNING}"
end tell

set US to (ASCII character 31)
set startDate to (current date)
set time of startDate to 0
set endDate to startDate + ({days} * days)

set bestCal to missing value
set bestCount to -1
tell application "Microsoft Outlook"
	-- Only the user's own Exchange calendar(s) are named "Calendar"; skipping the 60+
	-- colleague calendars keeps this fast (counting events on all of them times out).
	set candidates to (every calendar whose name is "Calendar")
	repeat with c in candidates
		set cnt to 0
		try
			set cnt to (count of (every calendar event of c whose start time ≥ startDate and start time ≤ endDate))
		end try
		if cnt > bestCount then
			set bestCount to cnt
			set bestCal to c
		end if
	end repeat
	if bestCal is missing value then return "ERR:no calendar named Calendar"
	set outLines to {{}}
	set evs to (every calendar event of bestCal whose start time ≥ startDate and start time ≤ endDate)
	repeat with e in evs
		set subj to ""
		try
			set subj to (subject of e) as string
		end try
		set loc to ""
		try
			set loc to (location of e) as string
		end try
		set ad to "false"
		try
			if (all day flag of e) then set ad to "true"
		end try
		set sd to (start time of e)
		set ed to (end time of e)
		set rec to subj & US & (year of sd) & US & ((month of sd) as integer) & US & (day of sd) & US & (hours of sd) & US & (minutes of sd) & US & (year of ed) & US & ((month of ed) as integer) & US & (day of ed) & US & (hours of ed) & US & (minutes of ed) & US & loc & US & ad
		set end of outLines to rec
	end repeat
end tell
set AppleScript's text item delimiters to linefeed
return outLines as string'''


def get_outlook_events(days: int = 14) -> list[dict]:
    """Return the work calendar's events for the next ``days`` days (local time).

    Raises OutlookError if Outlook isn't running / not in Legacy mode / osascript fails.
    Each event: {key, summary, start, end, location, all_day}.
    """
    script = _build_applescript(days)
    result = run_cli(["osascript", "-e", script], check=False, timeout=_DEFAULT_TIMEOUT)
    if getattr(result, "returncode", 0) != 0:
        err = (getattr(result, "stderr", "") or "osascript failed").strip()
        raise OutlookError(err)
    out = (getattr(result, "stdout", "") or "").strip()
    if out.startswith(OUTLOOK_NOT_RUNNING):
        raise OutlookError(
            "Microsoft Outlook isn't running, or it's in New Outlook mode. "
            "Open Outlook in Legacy mode (turn off the 'New Outlook' toggle)."
        )
    if out.startswith("ERR:"):
        raise OutlookError(out[len("ERR:"):].strip())
    return _parse_outlook_output(out)
