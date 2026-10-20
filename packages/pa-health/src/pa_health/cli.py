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

    args = parser.parse_args()
    try:
        if args.command == "day":
            cmd_day(args)
        elif args.command == "activities":
            cmd_activities(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
