"""Daily event logging for PA — records actions across sessions."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from pa_core.config import PA_ROOT

DAILY_DIR = PA_ROOT / "activity" / "daily"

# One session ID per process — groups events from a single Claude session
_SESSION_ID = uuid.uuid4().hex[:8]

CATEGORIES = {"email", "task", "calendar", "info", "wellness", "habit", "other"}


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _log_path(date: str | None = None) -> Path:
    return DAILY_DIR / f"{date or _today_str()}.json"


def _load_day(date: str | None = None) -> dict:
    path = _log_path(date)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"date": date or _today_str(), "events": []}


def _save_day(data: dict) -> Path:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = _log_path(data["date"])
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def log_event(
    category: str,
    action: str,
    summary: str,
    details: dict | None = None,
    project: str | None = None,
    links: dict[str, str] | None = None,
) -> dict:
    """Append an event to today's daily log. Returns the event dict.

    Args:
        links: Optional dict of {label: url} for resources created/referenced.
               e.g. {"event": "https://calendar.google.com/...", "task": "https://notion.so/..."}
    """
    if category not in CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {CATEGORIES}")

    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "session_id": _SESSION_ID,
        "category": category,
        "action": action,
        "summary": summary,
        "details": details or {},
        "project": project,
    }
    if links:
        event["links"] = links

    data = _load_day()
    data["events"].append(event)
    _save_day(data)
    return event


def get_today_events() -> list[dict]:
    """Return today's events."""
    return _load_day()["events"]


def get_events(date: str) -> list[dict]:
    """Return events for a specific date (YYYY-MM-DD)."""
    return _load_day(date)["events"]
