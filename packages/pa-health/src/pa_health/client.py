"""Health data from Garmin, normalised to a stable shape.

Consumers depend on the shape below, never on Garmin. If the source changes or
a different one is swapped in, only this module moves.

Why Garmin directly rather than Google Health Connect: Garmin deliberately
withholds its proprietary metrics from Health Connect. Body Battery and HRV
Status do not sync, so a Health Connect route is structurally incapable of
supplying the recovery signal the coaching logic needs. See ADR 0001,
amendment 4.

Reliability: the library authenticates by impersonating a browser TLS
fingerprint, because Garmin has no personal API. It broke once in March 2026
when Garmin tightened detection, and it will break again. Every fetch is
wrapped: a failure degrades to missing data. A briefing must never fail
because a watch did not sync.
"""
from __future__ import annotations

import datetime
from typing import Any
from zoneinfo import ZoneInfo

# Garmin timestamps are epoch ms. The user reads these against their own day, so they
# are rendered in local time, never UTC.
LOCAL_TZ = ZoneInfo("Europe/London")

# The contract. Every key is always present so consumers never need .get().
EMPTY: dict[str, Any] = {
    "date": None,
    "sleep_hours": None,
    "sleep_quality": None,
    "resting_hr": None,
    "hrv": None,
    "avg_stress": None,
    "max_stress": None,
    "body_battery_high": None,
    "body_battery_low": None,
    "steps": None,
    # Logged sessions (runs, rides, gym). Always a list, never None, so
    # callers can iterate without a guard. See normalise_activity().
    "activities": [],
    # Garmin's own high-HR alerts ("abnormal heart rate detected"). Fired when
    # HR crosses the user threshold while the watch believes you are at rest,
    # so most of these are arousal, not exertion. See AGENTS.md.
    "abnormal_hr": [],
    "source": "garmin",
    "ok": False,
}


def _dig(payload: Any, *path: str) -> Any:
    """Walk nested keys, returning None on anything unexpected.

    Half-synced watches return odd shapes — nulls where dicts should be, lists
    where objects should be. Every accessor goes through here.
    """
    cur = payload
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def normalise(
    date_str: str,
    sleep: Any = None,
    rhr: Any = None,
    hrv: Any = None,
    stress: Any = None,
    battery: Any = None,
    steps: Any = None,
    activities: Any = None,
    heart_rates: Any = None,
) -> dict[str, Any]:
    """Turn raw Garmin payloads into the stable shape. Never raises."""
    out = dict(EMPTY)
    out["date"] = date_str

    seconds = _dig(sleep, "dailySleepDTO", "sleepTimeSeconds")
    if isinstance(seconds, (int, float)) and seconds > 0:
        out["sleep_hours"] = round(seconds / 3600, 1)

    quality = _dig(sleep, "dailySleepDTO", "sleepScores", "overall", "qualifierKey")
    if isinstance(quality, str):
        out["sleep_quality"] = quality

    metrics = _dig(rhr, "allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE")
    if isinstance(metrics, list) and metrics:
        value = metrics[0].get("value") if isinstance(metrics[0], dict) else None
        if isinstance(value, (int, float)):
            out["resting_hr"] = int(value)

    # The 7-day average, not last night. A single night is too noisy to coach
    # from, and Garmin's own guidance treats the weekly figure as the signal.
    #
    # NOTE: this endpoint can return {} for an account, so `hrv` is always None.
    # Read HRV from `avg_stress` below instead — Garmin derives its stress score
    # from HRV, so it is the same signal on an inverted scale (lower = better
    # recovery). See packages/pa-health/AGENTS.md.
    weekly = _dig(hrv, "hrvSummary", "weeklyAvg")
    if isinstance(weekly, (int, float)):
        out["hrv"] = int(weekly)

    average_stress = _dig(stress, "avgStressLevel")
    maximum_stress = _dig(stress, "maxStressLevel")
    if isinstance(average_stress, (int, float)):
        out["avg_stress"] = int(average_stress)
    if isinstance(maximum_stress, (int, float)):
        out["max_stress"] = int(maximum_stress)

    if isinstance(battery, list) and battery and isinstance(battery[0], dict):
        high = battery[0].get("charged")
        low = battery[0].get("drained")
        if isinstance(high, (int, float)):
            out["body_battery_high"] = int(high)
        if isinstance(low, (int, float)):
            out["body_battery_low"] = int(low)

    if isinstance(steps, (int, float)) and steps > 0:
        out["steps"] = int(steps)

    if isinstance(activities, list):
        out["activities"] = [
            normalise_activity(a) for a in activities if isinstance(a, dict)
        ]

    out["abnormal_hr"] = normalise_abnormal_hr(date_str, heart_rates)

    out["ok"] = any(
        out[k] is not None
        for k in (
            "sleep_hours", "resting_hr", "hrv", "avg_stress",
            "body_battery_high", "steps",
        )
    ) or bool(out["activities"]) or bool(out["abnormal_hr"])
    return out


def normalise_abnormal_hr(date_str: str, heart_rates: Any) -> list[dict[str, Any]]:
    """Garmin's high-heart-rate alerts for one day, in local time.

    These are Garmin's own alerts, not a reconstruction: it stores the ones it
    fired in `abnormalHRValuesArray` as [epoch_ms, bpm] pairs, with the user's
    trigger threshold alongside.

    They matter because the calendar often cannot explain them. Surfacing them
    so the user can say what happened is the only way to label them.
    """
    threshold = _dig(heart_rates, "abnormalHrThresholdValue")
    values = _dig(heart_rates, "abnormalHRValuesArray")
    if not isinstance(values, list):
        return []

    events = []
    for pair in values:
        if not (isinstance(pair, (list, tuple)) and len(pair) >= 2):
            continue
        stamp, bpm = pair[0], pair[1]
        if not (isinstance(stamp, (int, float)) and isinstance(bpm, (int, float))):
            continue
        when = datetime.datetime.fromtimestamp(stamp / 1000, LOCAL_TZ)
        events.append({
            "ts": int(stamp),
            "date": when.strftime("%Y-%m-%d"),
            "time": when.strftime("%H:%M"),
            "bpm": int(bpm),
            "threshold": int(threshold) if isinstance(threshold, (int, float)) else None,
        })
    # Garmin does not guarantee order, and these are read as a timeline.
    events.sort(key=lambda e: e["ts"])
    return events


def normalise_activity(raw: dict[str, Any]) -> dict[str, Any]:
    """One Garmin activity, reduced to the fields the coaching layer uses.

    Garmin returns ~90 keys per activity, most of them plumbing (owner profile
    image URLs, dive flags, OAuth scopes). Everything below is either something
    the user would recognise about the session or something the coaching logic reads.

    Distance is absent for strength, yoga and similar, so it stays None rather
    than becoming 0.0 — a 0 km run and a gym session are not the same thing.
    """
    def num(key: str) -> float | None:
        value = raw.get(key)
        return value if isinstance(value, (int, float)) else None

    distance = num("distance")
    duration = num("duration")
    moderate = num("moderateIntensityMinutes") or 0
    vigorous = num("vigorousIntensityMinutes") or 0
    hr_avg, hr_max = num("averageHR"), num("maxHR")
    calories, vo2 = num("calories"), num("vO2MaxValue")

    return {
        "id": raw.get("activityId"),
        "name": raw.get("activityName"),
        "type": _dig(raw, "activityType", "typeKey"),
        "start": raw.get("startTimeLocal"),
        "distance_km": round(distance / 1000, 2) if distance else None,
        "duration_min": round(duration / 60, 1) if duration else None,
        "avg_hr": int(hr_avg) if hr_avg else None,
        "max_hr": int(hr_max) if hr_max else None,
        "calories": int(calories) if calories else None,
        "vo2max": int(vo2) if vo2 else None,
        # Garmin splits these but the useful number is the total, which is what
        # the WHO 150-minutes-a-week guideline is expressed in.
        "intensity_minutes": int(moderate + vigorous),
        "is_pr": bool(raw.get("isPR")),
    }


def weekly_summary(activities: Any) -> dict[str, Any]:
    """Running totals across a set of normalised activities.

    When building a running habit, weekly volume is the number that matters,
    not any single run.

    Average heart rate is weighted by duration: a 60-minute run says twice as
    much about the week's effort as a 30-minute one, and a plain mean of the
    two would flatter a week of short hard efforts. Runs without heart rate
    (manually logged ones, when the watch was flat) still count toward distance
    but are left out of the average rather than counted as zero.
    """
    empty = {"runs": 0, "distance_km": 0.0, "duration_min": 0.0, "avg_hr": None}
    if not isinstance(activities, list):
        return empty

    runs = [a for a in activities if isinstance(a, dict) and a.get("type") == "running"]
    if not runs:
        return empty

    def num(a, key):
        v = a.get(key)
        return float(v) if isinstance(v, (int, float)) else 0.0

    distance = sum(num(a, "distance_km") for a in runs)
    duration = sum(num(a, "duration_min") for a in runs)

    weighted = [(a, num(a, "duration_min")) for a in runs
                if isinstance(a.get("avg_hr"), (int, float)) and num(a, "duration_min") > 0]
    avg_hr = None
    if weighted:
        total = sum(mins for _, mins in weighted)
        avg_hr = round(sum(a["avg_hr"] * mins for a, mins in weighted) / total)

    return {
        "runs": len(runs),
        "distance_km": round(distance, 2),
        "duration_min": round(duration, 1),
        "avg_hr": avg_hr,
    }


def get_activities_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Normalised activities between two dates inclusive. Never raises."""
    try:
        client = _authenticated_client()
        raw = client.get_activities_by_date(start_date, end_date)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [normalise_activity(a) for a in raw if isinstance(a, dict)]


def get_health(date_str: str | None = None) -> dict[str, Any]:
    """Fetch and normalise one day of health data.

    Returns the EMPTY shape with ok=False rather than raising, whatever goes
    wrong — no credentials, expired tokens, Garmin blocking the login, a
    changed payload. Callers check `ok`.
    """
    from pa_core.config import get_now

    date_str = date_str or get_now()["date"]

    try:
        client = _authenticated_client()
    except Exception:
        return {**EMPTY, "date": date_str}

    def safe(fn, *args):
        try:
            return fn(*args)
        except Exception:
            return None

    return normalise(
        date_str,
        sleep=safe(client.get_sleep_data, date_str),
        rhr=safe(client.get_rhr_day, date_str),
        hrv=safe(client.get_hrv_data, date_str),
        stress=safe(client.get_all_day_stress, date_str),
        battery=safe(client.get_body_battery, date_str),
        steps=safe(_total_steps, client, date_str),
        activities=safe(client.get_activities_by_date, date_str, date_str),
        heart_rates=safe(client.get_heart_rates, date_str),
    )


def _total_steps(client, date_str: str) -> int | None:
    data = client.get_steps_data(date_str)
    if not isinstance(data, list):
        return None
    return sum(d.get("steps", 0) for d in data if isinstance(d, dict)) or None


def _authenticated_client():
    """Resume a cached Garmin session, falling back to a fresh login.

    `login(tokenstore)` loads the cached token if present and writes it back
    after a fresh login, so the login flow — the fragile part, the part Garmin
    rate-limits and actively defends against — runs rarely rather than daily.
    Hitting it every fetch is what earns a 429.

    Note there is no `garth` attribute any more: the library dropped garth in
    2026 and rebuilt auth on curl_cffi TLS impersonation. Persistence lives on
    `client`, via the tokenstore path passed to login().
    """
    from garminconnect import Garmin

    from pa_core.config import get_secret

    token_dir = _token_dir()
    token_dir.mkdir(parents=True, exist_ok=True)
    store = str(token_dir)

    # Cached-token path first: no credentials needed, no login request made.
    try:
        client = Garmin()
        client.login(store)
        return client
    except Exception:
        pass

    client = Garmin(get_secret("GARMIN_EMAIL"), get_secret("GARMIN_PASSWORD"))
    needs_mfa, _ = client.login(store)
    if needs_mfa:
        raise RuntimeError(
            "Garmin needs an MFA code — run a login interactively once to mint the token"
        )
    return client


def _token_dir():
    from pathlib import Path
    return Path.home() / ".garminconnect"
