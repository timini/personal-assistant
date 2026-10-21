"""Structured training log: one record per exercise session, planned or done.

Stored as JSON lines at activity/training/sessions.jsonl ($PA_TRAINING_FILE
overrides it). The daily event log stays for check-ins and habits; this log is
the history a coach reads: what was planned, what happened, sets and weights,
and Garmin metrics for the same session.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path

TYPES = ("run", "strength", "climb", "yoga", "walk", "cycle", "swim", "tennis", "other")
STATUSES = ("planned", "done", "missed", "skipped")

# Garmin activityType.typeKey to session type. Anything else becomes "other".
GARMIN_TYPES = {
    "running": "run", "treadmill_running": "run", "trail_running": "run", "track_running": "run",
    "indoor_running": "run", "strength_training": "strength", "indoor_cardio": "strength",
    "indoor_climbing": "climb", "bouldering": "climb", "rock_climbing": "climb",
    "yoga": "yoga", "pilates": "yoga", "walking": "walk", "hiking": "walk",
    "cycling": "cycle", "road_biking": "cycle", "indoor_cycling": "cycle", "virtual_ride": "cycle",
    "mountain_biking": "cycle", "lap_swimming": "swim", "open_water_swimming": "swim",
    "tennis": "tennis",
}

# Garmin records these as activities, but they are not training.
GARMIN_SKIP = {"breathwork", "meditation"}

GARMIN_FIELDS = ("duration_min", "distance_km", "avg_hr", "max_hr", "training_load", "aerobic_te")

_EMPTY_SESSION = {
    "id": None, "date": None, "time": None, "type": None, "status": "planned", "source": "user",
    "garmin_id": None, "garmin_name": None, "duration_min": None, "distance_km": None,
    "avg_hr": None, "max_hr": None, "training_load": None, "aerobic_te": None,
    "rpe": None, "feel": None, "notes": None, "exercises": [],
}


def _file() -> Path:
    override = os.environ.get("PA_TRAINING_FILE")
    if override:
        return Path(override)
    import pa_core.config as config
    return config.PA_ROOT / "activity" / "training" / "sessions.jsonl"


def _load() -> list[dict]:
    path = _file()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _save(sessions: list[dict]) -> None:
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    sessions = sorted(sessions, key=lambda s: (s["date"], s.get("time") or "", s["id"]))
    path.write_text("".join(json.dumps(s) + "\n" for s in sessions))


def _today() -> str:
    from pa_core.config import get_now
    return get_now()["date"]


def _check_type(type_: str | None) -> None:
    if type_ is not None and type_ not in TYPES:
        raise ValueError(f"Unknown type {type_!r}; use one of {', '.join(TYPES)}")


def _new_id(sessions: list[dict], date: str) -> str:
    n = 1 + sum(1 for s in sessions if s["date"] == date)
    while any(s["id"] == f"{date}-{n}" for s in sessions):
        n += 1
    return f"{date}-{n}"


_SET = re.compile(r"^(?:(\d+)x)?(\d+)(?:@(\d+(?:\.\d+)?)(?:kg)?)?(/side)?$")


def parse_exercise(spec: str) -> dict:
    """'bench press=3x10@50', 'curl=3x10@10/side', 'bench=12@40,10@45' or 'pull up=3x5'."""
    name, sep, sets_part = spec.partition("=")
    name = name.strip()
    if not sep or not name or not sets_part.strip():
        raise ValueError(f"Exercise must look like 'bench press=3x10@50', got {spec!r}")
    sets = []
    for chunk in sets_part.replace(" ", "").split(","):
        match = _SET.match(chunk)
        if not match:
            raise ValueError(f"Cannot read sets {chunk!r} in {spec!r}; use 3x10@50 or 12@40,10@45")
        count, reps, weight, side = match.groups()
        sets += [{"reps": int(reps), "weight_kg": float(weight) if weight else None,
                  "per_side": bool(side)}] * int(count or 1)
    return {"name": name, "sets": sets}


def _tick_habit(session: dict, today: str) -> None:
    """Mark today's Exercise habit done, once, when today's session is done."""
    if session["status"] != "done" or session["date"] != today:
        return
    from pa_core import daily_log
    from pa_core.config import get_user_config
    habit = (get_user_config().get("training") or {}).get("habit", "Exercise")
    for event in daily_log.get_events(today):
        if event.get("category") == "habit" and event.get("summary") == habit \
                and event.get("action") == "completed":
            return
    daily_log.log_event("habit", "completed", habit,
                        details={"training_session": session["id"], "type": session["type"]})


def plan(date: str, time: str | None = None, type: str | None = None, notes: str | None = None) -> dict:
    """Record an agreed session. The type may be chosen later."""
    _check_type(type)
    sessions = _load()
    session = {**_EMPTY_SESSION, "id": _new_id(sessions, date), "date": date, "time": time,
               "type": type, "notes": notes, "exercises": []}
    _save(sessions + [session])
    return session


def log(type: str, date: str | None = None, *, time: str | None = None, exercises: list[dict] | None = None,
        rpe: int | None = None, feel: str | None = None, duration_min: float | None = None,
        distance_km: float | None = None, notes: str | None = None, today: str | None = None) -> dict:
    """Record a finished session, closing that day's matching plan if there is one."""
    _check_type(type)
    today = today or _today()
    date = date or today
    sessions = _load()
    plans = [s for s in sessions if s["date"] == date and s["status"] == "planned"]
    session = next((s for s in plans if s["type"] == type), None) or \
        next((s for s in plans if s["type"] is None), None)
    if session is None:
        session = {**_EMPTY_SESSION, "id": _new_id(sessions, date), "date": date, "exercises": []}
        sessions.append(session)
    session.update(type=type, status="done")
    session["exercises"] = session["exercises"] + (exercises or [])
    for key, value in (("time", time), ("rpe", rpe), ("feel", feel), ("duration_min", duration_min),
                       ("distance_km", distance_km), ("notes", notes)):
        if value is not None:
            session[key] = value
    _save(sessions)
    _tick_habit(session, today)
    return session


def update(session_id: str, *, status: str | None = None, type: str | None = None,
           exercises: list[dict] | None = None, rpe: int | None = None, feel: str | None = None,
           notes: str | None = None, duration_min: float | None = None, today: str | None = None) -> dict:
    """Change a session: close a plan as done or missed, add sets, record RPE."""
    if status is not None and status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}; use one of {', '.join(STATUSES)}")
    _check_type(type)
    sessions = _load()
    session = next((s for s in sessions if s["id"] == session_id), None)
    if session is None:
        raise KeyError(f"No training session {session_id!r}")
    for key, value in (("status", status), ("type", type), ("rpe", rpe), ("feel", feel),
                       ("notes", notes), ("duration_min", duration_min)):
        if value is not None:
            session[key] = value
    if exercises:
        session["exercises"] = session["exercises"] + exercises
    _save(sessions)
    _tick_habit(session, today or _today())
    return session


def sessions(start: str | None = None, end: str | None = None, type: str | None = None) -> list[dict]:
    return [s for s in _load()
            if (start is None or s["date"] >= start) and (end is None or s["date"] <= end)
            and (type is None or s["type"] == type)]


def unresolved_plans(today: str) -> list[dict]:
    """Plans whose day has passed without being marked done, missed or skipped."""
    return [s for s in _load() if s["status"] == "planned" and s["date"] < today]


def sync_activities(activities: list[dict]) -> dict:
    """Import normalised Garmin activities. Re-running adds nothing; never ticks habits.

    Dates come from Garmin's startTimeLocal, the watch's own local time, so they
    match the user's day without conversion.
    """
    sessions = _load()
    counts = {"added": 0, "merged": 0, "skipped": 0}
    for activity in activities:
        if not activity.get("id") or not activity.get("start"):
            continue
        if activity.get("type") in GARMIN_SKIP or any(s["garmin_id"] == activity["id"] for s in sessions):
            counts["skipped"] += 1
            continue
        date, time = activity["start"][:10], activity["start"][11:16] or None
        type_ = GARMIN_TYPES.get(activity.get("type") or "", "other")
        candidates = [s for s in sessions if s["date"] == date and s["garmin_id"] is None
                      and s["status"] in ("planned", "done")]
        session = next((s for s in candidates if s["type"] == type_), None) or \
            next((s for s in candidates if s["type"] is None), None)
        if session is None:
            session = {**_EMPTY_SESSION, "id": _new_id(sessions, date), "date": date, "time": time,
                       "type": type_, "source": "garmin", "exercises": []}
            sessions.append(session)
            counts["added"] += 1
        else:
            session["source"] = "both"
            session["type"] = type_
            session["time"] = session["time"] or time
            counts["merged"] += 1
        session.update(status="done", garmin_id=activity["id"], garmin_name=activity.get("name"))
        for key in GARMIN_FIELDS:
            if session.get(key) is None and activity.get(key) is not None:
                session[key] = activity[key]
    _save(sessions)
    return counts


def _volume(sets: list[dict]) -> float:
    return sum(s["reps"] * (s["weight_kg"] or 0) * (2 if s["per_side"] else 1) for s in sets)


def exercise_history(name: str) -> list[dict]:
    """Per-session progress for exercises whose name contains `name` (any case)."""
    needle = name.lower()
    history = []
    for s in _load():
        sets = [st for ex in s["exercises"] if needle in ex["name"].lower() for st in ex["sets"]]
        if not sets or s["status"] != "done":
            continue
        weights = [st["weight_kg"] for st in sets if st["weight_kg"] is not None]
        best = max(sets, key=lambda st: (st["weight_kg"] or 0, st["reps"]))
        history.append({"date": s["date"], "session": s["id"], "sets": len(sets),
                        "top_weight_kg": max(weights) if weights else None,
                        "best_set": best, "volume_kg": _volume(sets), "rpe": s.get("rpe")})
    return history


def week_summary(end: str, days: int = 7) -> dict:
    end_d = datetime.date.fromisoformat(end)
    start = (end_d - datetime.timedelta(days=days - 1)).isoformat()
    done = [s for s in sessions(start, end) if s["status"] == "done"]
    by_type: dict[str, int] = {}
    for s in done:
        by_type[s["type"] or "other"] = by_type.get(s["type"] or "other", 0) + 1
    every_done = [s for s in _load() if s["status"] == "done" and s["date"] <= end]
    last = every_done[-1] if every_done else None
    return {
        "start": start, "end": end, "sessions": len(done), "by_type": by_type,
        "minutes": round(sum(s["duration_min"] or 0 for s in done), 1),
        "km": round(sum(s["distance_km"] or 0 for s in done), 2),
        "last_session": last,
        "days_since_last": (end_d - datetime.date.fromisoformat(last["date"])).days if last else None,
        "missed": sum(1 for s in sessions(start, end) if s["status"] == "missed"),
        "planned_today": [s for s in sessions(end, end) if s["status"] == "planned"],
        "unresolved": unresolved_plans(end),
    }


def brief_line(today: str) -> str:
    """One line for the session-start brief."""
    week = week_summary(today)
    last = week["last_session"]
    if week["sessions"]:
        line = (f"Exercise: last session {last['date']} ({last['type']}), "
                f"{week['sessions']} in the last 7 days.")
    else:
        since = f" Last session {last['date']} ({last['type']})." if last else ""
        line = f"Exercise: nothing logged in the last 7 days.{since} Load the personal-trainer skill to plan a session."
    if week["planned_today"]:
        plans = ", ".join(f"{p['time'] or 'time not set'} ({p['type'] or 'activity not chosen'})"
                          for p in week["planned_today"])
        line += f" Planned today: {plans}."
    if week["unresolved"]:
        plans = ", ".join(f"{p['date']} {p['type'] or 'session'}" for p in week["unresolved"])
        line += f" Unresolved plans: {plans}; ask what happened."
    return line
