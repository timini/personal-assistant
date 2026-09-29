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

from typing import Any

# The contract. Every key is always present so consumers never need .get().
EMPTY: dict[str, Any] = {
    "date": None,
    "sleep_hours": None,
    "sleep_quality": None,
    "resting_hr": None,
    "hrv": None,
    "body_battery_high": None,
    "body_battery_low": None,
    "steps": None,
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
    battery: Any = None,
    steps: Any = None,
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
    weekly = _dig(hrv, "hrvSummary", "weeklyAvg")
    if isinstance(weekly, (int, float)):
        out["hrv"] = int(weekly)

    if isinstance(battery, list) and battery and isinstance(battery[0], dict):
        high = battery[0].get("charged")
        low = battery[0].get("drained")
        if isinstance(high, (int, float)):
            out["body_battery_high"] = int(high)
        if isinstance(low, (int, float)):
            out["body_battery_low"] = int(low)

    if isinstance(steps, (int, float)) and steps > 0:
        out["steps"] = int(steps)

    out["ok"] = any(
        out[k] is not None
        for k in ("sleep_hours", "resting_hr", "hrv", "body_battery_high", "steps")
    )
    return out


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
        battery=safe(client.get_body_battery, date_str),
        steps=safe(_total_steps, client, date_str),
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
