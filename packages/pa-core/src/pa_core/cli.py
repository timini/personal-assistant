"""PA Core CLI — setup, briefing, and event logging."""

import argparse
import sys


def cmd_setup(args):
    from pa_core.setup import setup
    setup()


def cmd_briefing(args):
    if args.evening:
        from pa_core.briefing import generate_evening_briefing, save_evening_briefing
        if args.save:
            path = save_evening_briefing(date=args.date)
            print(f"Saved to {path}")
        else:
            print(generate_evening_briefing(date=args.date))
        if args.telegram:
            try:
                from pa_telegram.client import send_evening_briefing
                send_evening_briefing(date=args.date)
                print("Evening briefing sent to Telegram.")
            except (ImportError, Exception) as exc:
                print(f"Telegram send failed: {exc}", file=sys.stderr)
    else:
        from pa_core.briefing import generate_briefing, save_briefing
        if args.save:
            path = save_briefing(date=args.date)
            print(f"Saved to {path}")
        else:
            print(generate_briefing(date=args.date))
        if args.telegram:
            try:
                from pa_telegram.client import send_briefing
                send_briefing(date=args.date)
                print("Briefing sent to Telegram.")
            except (ImportError, Exception) as exc:
                print(f"Telegram send failed: {exc}", file=sys.stderr)
    if args.backup:
        try:
            from pa_google.drive import run_backup
            result = run_backup()
            print(f"Backup uploaded: {result['filename']}")
        except (ImportError, Exception) as exc:
            print(f"Backup failed: {exc}", file=sys.stderr)


def cmd_log(args):
    from pa_core.daily_log import log_event
    event = log_event(
        category=args.category,
        action=args.action,
        summary=args.summary,
        project=args.project,
    )
    print(f"Logged: [{event['category']}] {event['action']} — {event['summary']}")


def main():
    parser = argparse.ArgumentParser(prog="pa-core", description="PA shared utilities")
    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Interactive first-run onboarding")

    # briefing
    bp = sub.add_parser("briefing", help="Generate daily briefing")
    bp.add_argument("--evening", action="store_true", help="Generate evening briefing instead of morning")
    bp.add_argument("--save", action="store_true", help="Save briefing to file")
    bp.add_argument("--date", default=None, help="Date (YYYY-MM-DD), defaults to today")
    bp.add_argument("--backup", action="store_true", help="Backup personal files after saving")
    bp.add_argument("--telegram", action="store_true", help="Send briefing to Telegram")

    # log
    lp = sub.add_parser("log", help="Log an event to today's daily log")
    lp.add_argument("category", help="Event category: email, task, calendar, info, other")
    lp.add_argument("action", help="Action: archived, created, completed, surfaced, flagged, etc.")
    lp.add_argument("summary", help="Short description of the event")
    lp.add_argument("--project", default=None, help="Associated project name")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "briefing":
        cmd_briefing(args)
    elif args.command == "log":
        cmd_log(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
