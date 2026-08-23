"""Persist today's context so sessions read it instead of refetching it.

`context.get_today_context()` already gathers calendar, inbox, tasks, habits,
weather and stats, each with its own error handling. What was missing is that
nothing wrote the result down — so every session paid to fetch all of it again,
inside an expensive agent loop, to arrive at the same answer.

This module adds the caching layer only. It does not fetch anything itself, and
deliberately does not reimplement any source. Per ADR 0001, this runs with no
model in the loop.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pa_core.config import PA_ROOT, get_now
from pa_core.context import get_today_context

STATE_DIR = PA_ROOT / "activity" / "state"

# Live queues that must never be served from cache — see collect().
LIVE_KEYS = ("telegram_messages", "whatsapp_messages")


def state_path(date_str: str) -> Path:
    return STATE_DIR / f"{date_str}.json"


def write_state(ctx: dict) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = state_path(ctx["date"])
    path.write_text(json.dumps(ctx, indent=2, default=str))
    return path


def read_state(
    date_str: str,
    max_age_minutes: int | None = None,
    now: str | None = None,
) -> dict | None:
    """Return the cached context, or None if absent or too old.

    With no max_age_minutes, age is ignored — an old file is still the right
    answer for a day that has finished.
    """
    path = state_path(date_str)
    if not path.exists():
        return None
    try:
        ctx = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    if max_age_minutes is None:
        return ctx

    stamped = ctx.get("collected_at")
    if not stamped:
        return None
    try:
        collected = datetime.fromisoformat(stamped)
        current = datetime.fromisoformat(now) if now else datetime.now()
    except ValueError:
        return None
    if current - collected > timedelta(minutes=max_age_minutes):
        return None
    return ctx


def collect() -> dict:
    """Gather today's context, stamp it, write it, return it.

    get_today_context() nests the date under "now"; it is lifted to the top
    level here so the state file is self-describing and state_path() has
    something to key on.
    """
    started = datetime.now()
    ctx = get_today_context()
    ctx["date"] = (ctx.get("now") or {}).get("date") or get_now()["date"]
    ctx["collected_at"] = started.isoformat(timespec="seconds")
    ctx["collect_seconds"] = round((datetime.now() - started).total_seconds(), 1)
    ctx["ok"] = not ctx.get("errors")

    # Message queues are live state, not context. Persisting them would mean a
    # later cache hit surfaces messages that have already been acknowledged,
    # and misses anything that arrived since. The caller gets them; the file
    # does not.
    cacheable = dict(ctx)
    for key in LIVE_KEYS:
        cacheable[key] = []
    write_state(cacheable)
    return ctx


def get_context(max_age_minutes: int | None = 60) -> dict:
    """Cached context for today, refetching only when stale.

    This is what a session or a scheduled run should call. The default hour
    means a morning briefing and anything else that morning share one fetch.
    """
    date_str = get_now()["date"]
    cached = read_state(date_str, max_age_minutes=max_age_minutes)
    if cached is None:
        return collect()

    # The cached file deliberately holds no messages; fetch those live so
    # anything downstream that acknowledges them sees the real queue.
    for key, fetch in (
        ("telegram_messages", _fetch_telegram),
        ("whatsapp_messages", _fetch_whatsapp),
    ):
        cached[key] = fetch()
    return cached


def _fetch_telegram() -> list:
    try:
        from pa_telegram.client import get_messages
        return get_messages()
    except Exception:
        return []


def _fetch_whatsapp() -> list:
    try:
        from pa_whatsapp.client import get_messages
        return get_messages()
    except Exception:
        return []
