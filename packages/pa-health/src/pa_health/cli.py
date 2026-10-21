"""CLI entry point for pa-health."""

import argparse
import json
import sys
from datetime import date, timedelta

from pa_health.client import get_activities_range, get_health

_READINGS = (
    ("Sleep", "sleep_hours", " h"), ("Sleep quality", "sleep_quality", ""),
    ("Resting HR", "resting_hr", " bpm"), ("HRV (weekly avg)", "hrv", " ms"),
    ("Stress avg/max", "avg_stress", ""), ("Body battery high", "body_battery_high", ""),
    ("Body battery low", "body_battery_low", ""), ("Steps", "steps", ""),
)


def _today() -> str:
    from pa_core.config import get_now
    return get_now()["date"]


def _activity_line(a: dict) -> str:
    distance = f"  {a['distance_km']} km" if a.get("distance_km") is not None else ""
    duration = f"  {a['duration_min']} min" if a.get("duration_min") is not None else ""
    hr = f"  avg HR {a['avg_hr']}" if a.get("avg_hr") else ""
    start = f"{a['start']}  " if a.get("start") else ""
    return f"  {start}{a.get('name') or a.get('type')}{distance}{duration}{hr}"


def cmd_day(args):
    day = get_health(args.date)
    if args.json:
        print(json.dumps(day, indent=2, default=str))
        return
    if not day.get("ok"):
        print(f"No health data for {day['date']} (not synced, or Garmin login failed).")
        return
    print(f"Health for {day['date']}")
    for label, key, unit in _READINGS:
        if day.get(key) is not None:
            value = f"{day[key]}/{day['max_stress']}" if key == "avg_stress" else day[key]
            print(f"  {label}: {value}{unit}")
    if day.get("activities"):
        print("Activities:")
        for a in day["activities"]:
            print(_activity_line(a))
    for alert in day.get("abnormal_hr") or []:
        print(f"  HR alert: {alert.get('time')} {alert.get('bpm')} bpm")


def cmd_activities(args):
    end = args.to or _today()
    start = args.from_ or (date.fromisoformat(end) - timedelta(days=args.days - 1)).isoformat()
    activities = get_activities_range(start, end)
    if args.json:
        print(json.dumps(activities, indent=2, default=str))
        return
    print(f"{len(activities)} activities from {start} to {end}")
    for a in activities:
        print(_activity_line(a))


def cmd_alerts(args):
    """Garmin abnormal-HR alerts not yet explained in the daily log."""
    from pa_core.context import unlabelled_hr_alerts
    from pa_core.daily_log import get_events
    end = date.fromisoformat(args.to or _today())
    alerts = []
    for offset in range(args.days - 1, -1, -1):
        day = (end - timedelta(days=offset)).isoformat()
        alerts += unlabelled_hr_alerts(get_health(day).get("abnormal_hr") or [], get_events(day))
    if args.json:
        print(json.dumps(alerts, indent=2, default=str))
        return
    if not alerts:
        print("No unexplained HR alerts.")
        return
    for a in alerts:
        print(f"  {a.get('date')} {a.get('time')}  {a.get('bpm')} bpm (threshold {a.get('threshold')})")
    print("Record each answer: uv run pa-core log wellness hr_context \"<what it was>\" "
          "--details '{\"date\": \"<date>\", \"time\": \"<time>\"}'")


def _sets_text(sets: list[dict]) -> str:
    def one(st):
        if st["weight_kg"] is None:
            return f"{st['reps']} reps"
        return f"{st['reps']}x{st['weight_kg']}kg" + (" per side" if st["per_side"] else "")
    if all(st == sets[0] for st in sets):
        return f"{len(sets)} sets, {one(sets[0])}"
    return ", ".join(one(st) for st in sets)


def _session_text(s: dict) -> str:
    parts = [f"{s['id']} {s['type'] or 'session'} ({s['status']})"]
    if s.get("time"):
        parts.append(s["time"])
    for key, label in (("duration_min", " min"), ("distance_km", " km"), ("avg_hr", " bpm avg")):
        if s.get(key) is not None:
            parts.append(f"{s[key]}{label}")
    if s.get("rpe") is not None:
        parts.append(f"RPE {s['rpe']}")
    lines = ["  ".join(parts)]
    lines += [f"  {ex['name']}: {_sets_text(ex['sets'])}" for ex in s.get("exercises") or []]
    for key in ("feel", "notes"):
        if s.get(key):
            lines.append(f"  {key}: {s[key]}")
    return "\n".join(lines)


def cmd_workout(args):
    """Structured training log; see the personal-trainer skill."""
    from pa_core import training
    exercises = []
    if args.workout_command in ("log", "update"):
        exercises = [training.parse_exercise(e) for e in args.exercise or []]
    if args.workout_command == "plan":
        s = training.plan(args.date, time=args.time, type=args.type, notes=args.note)
        print(f"Planned {s['id']}  {s['time'] or 'time not set'}  {s['type'] or 'activity not chosen'}")
    elif args.workout_command == "log":
        s = training.log(args.type, date=args.date, time=args.time, exercises=exercises, rpe=args.rpe,
                         feel=args.feel, duration_min=args.duration, distance_km=args.distance,
                         notes=args.notes)
        print(f"Logged {_session_text(s)}")
    elif args.workout_command == "update":
        s = training.update(args.id, status=args.status, type=args.type, exercises=exercises, rpe=args.rpe,
                            feel=args.feel, notes=args.notes, duration_min=args.duration)
        print(f"Updated {_session_text(s)}")
    elif args.workout_command == "sync":
        end = args.to or _today()
        start = args.from_ or (date.fromisoformat(end) - timedelta(days=args.days - 1)).isoformat()
        counts = training.sync_activities(get_activities_range(start, end))
        print(f"Garmin sync {start} to {end}: {counts['added']} added, {counts['merged']} merged, "
              f"{counts['skipped']} already logged")
    elif args.workout_command == "history":
        if args.exercise:
            rows = training.exercise_history(args.exercise)
            if args.json:
                print(json.dumps(rows, indent=2))
                return
            for h in rows:
                best, top = h["best_set"], h["top_weight_kg"]
                best_text = f"{best['reps']}x{best['weight_kg']}kg" if best["weight_kg"] is not None else f"{best['reps']} reps"
                rpe = f"  RPE {h['rpe']}" if h.get("rpe") is not None else ""
                print(f"{h['date']}  {h['sets']} sets  top {top if top is not None else '-'} kg  "
                      f"best {best_text}  volume {h['volume_kg']:.0f} kg{rpe}")
            if not rows:
                print(f"No logged sets for {args.exercise!r}.")
            return
        end = _today()
        start = (date.fromisoformat(end) - timedelta(days=args.days - 1)).isoformat()
        rows = training.sessions(start, end, type=args.type)
        if args.json:
            print(json.dumps(rows, indent=2))
            return
        print(f"{len(rows)} sessions from {start} to {end}")
        for s in rows:
            print(_session_text(s))
    elif args.workout_command == "week":
        week = training.week_summary(args.to or _today())
        if args.json:
            print(json.dumps(week, indent=2))
            return
        by_type = ", ".join(f"{n} {t}" for t, n in sorted(week["by_type"].items())) or "none"
        print(f"{week['start']} to {week['end']}: {week['sessions']} sessions ({by_type}), "
              f"{week['minutes']} min, {week['km']} km, {week['missed']} missed")
        if week["last_session"]:
            print(f"Last session: {week['last_session']['date']} {week['last_session']['type']} "
                  f"({week['days_since_last']} days ago)")
        for p in week["planned_today"]:
            print(f"Planned today: {_session_text(p)}")
        for p in week["unresolved"]:
            print(f"Unresolved plan: {_session_text(p)}  (ask what happened, then update --status)")


def main():
    parser = argparse.ArgumentParser(prog="pa-health", description="Garmin health and activity data")
    sub = parser.add_subparsers(dest="command", required=True)

    day_p = sub.add_parser("day", help="One day's sleep, HR, HRV, stress, steps and activities")
    day_p.add_argument("--date", help="YYYY-MM-DD (default today)")
    day_p.add_argument("--json", action="store_true")

    act_p = sub.add_parser("activities", help="Recorded activities over a date range")
    act_p.add_argument("--days", type=int, default=7, help="Number of days up to --to (default 7)")
    act_p.add_argument("--from", dest="from_", help="Start date YYYY-MM-DD (overrides --days)")
    act_p.add_argument("--to", help="End date YYYY-MM-DD (default today)")
    act_p.add_argument("--json", action="store_true")

    al_p = sub.add_parser("alerts", help="Abnormal-HR alerts not yet explained in the daily log")
    al_p.add_argument("--days", type=int, default=2, help="Number of days up to --to (default 2)")
    al_p.add_argument("--to", help="End date YYYY-MM-DD (default today)")
    al_p.add_argument("--json", action="store_true")

    from pa_core.training import STATUSES, TYPES
    wk = sub.add_parser("workout", help="Structured training log: plan, log, sync from Garmin, progress")
    wsub = wk.add_subparsers(dest="workout_command", required=True)
    wp = wsub.add_parser("plan", help="Record an agreed session (type can be chosen later)")
    wp.add_argument("--date", required=True)
    wp.add_argument("--time", help="HH:MM")
    wp.add_argument("--type", choices=TYPES)
    wp.add_argument("--note")
    wl = wsub.add_parser("log", help="Record a finished session; closes that day's matching plan")
    wl.add_argument("--type", required=True, choices=TYPES)
    wl.add_argument("--date", help="YYYY-MM-DD (default today)")
    wl.add_argument("--time", help="HH:MM")
    wl.add_argument("--exercise", action="append", help="'bench press=3x10@50', 'curl=3x10@10/side'; repeat")
    wl.add_argument("--rpe", type=int, choices=range(1, 11), metavar="1-10")
    wl.add_argument("--feel", help="How it felt, in the user's words")
    wl.add_argument("--duration", type=float, help="Minutes")
    wl.add_argument("--distance", type=float, help="Kilometres")
    wl.add_argument("--notes")
    wu = wsub.add_parser("update", help="Close a plan as done, missed or skipped, add sets, record RPE")
    wu.add_argument("id")
    wu.add_argument("--status", choices=STATUSES)
    wu.add_argument("--type", choices=TYPES)
    wu.add_argument("--exercise", action="append", help="Add sets: 'bench press=3x10@50'; repeat")
    wu.add_argument("--rpe", type=int, choices=range(1, 11), metavar="1-10")
    wu.add_argument("--feel")
    wu.add_argument("--duration", type=float, help="Minutes")
    wu.add_argument("--notes")
    ws = wsub.add_parser("sync", help="Import Garmin activities; safe to re-run")
    ws.add_argument("--days", type=int, default=7)
    ws.add_argument("--from", dest="from_", help="Start date YYYY-MM-DD (overrides --days)")
    ws.add_argument("--to", help="End date YYYY-MM-DD (default today)")
    wh = wsub.add_parser("history", help="Recent sessions, or progress for one exercise")
    wh.add_argument("--days", type=int, default=28)
    wh.add_argument("--type", choices=TYPES)
    wh.add_argument("--exercise", help="Name or part of it, e.g. bench")
    wh.add_argument("--json", action="store_true")
    ww = wsub.add_parser("week", help="Sessions, minutes and km over 7 days, plus open plans")
    ww.add_argument("--to", help="End date YYYY-MM-DD (default today)")
    ww.add_argument("--json", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "day":
            cmd_day(args)
        elif args.command == "activities":
            cmd_activities(args)
        elif args.command == "alerts":
            cmd_alerts(args)
        elif args.command == "workout":
            cmd_workout(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
