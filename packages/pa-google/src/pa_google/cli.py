"""CLI entry point for pa-google."""

import argparse
import json
import sys

from pa_google.gmail import get_inbox_emails
from pa_google.calendar import (
    get_all_todays_events,
    get_all_upcoming_events,
    check_calendars,
)


def _format_event(e: dict) -> str:
    """Format event for display with optional calendar label."""
    time_str = e["start"].split("T")[1][:5] if "T" in e["start"] else e["start"]
    label = e.get("calendar")
    label_str = f" [{label}]" if label else ""
    return f"  {time_str}{label_str}  {e['summary']}"


def cmd_briefing(args):
    """Generate a morning briefing: today's events + unread emails."""
    print("=== Calendar: Today ===\n")
    try:
        events = get_all_todays_events()
        if events:
            for e in events:
                print(_format_event(e))
        else:
            print("  No events today.")
    except Exception as e:
        print(f"  Error fetching calendar: {e}", file=sys.stderr)

    print("\n=== Inbox Emails ===\n")
    try:
        emails = get_inbox_emails(limit=10)
        if emails:
            for em in emails:
                print(f"  From: {em['from']}")
                print(f"  Subject: {em['subject']}")
                print(f"  {em['snippet'][:100]}")
                print()
        else:
            print("  No unread emails.")
    except Exception as e:
        print(f"  Error fetching emails: {e}", file=sys.stderr)


def cmd_emails(args):
    """List inbox emails."""
    try:
        emails = get_inbox_emails(limit=args.limit, unread_only=args.unread)
        if args.json:
            print(json.dumps(emails, indent=2))
        else:
            for em in emails:
                print(f"From: {em['from']}")
                print(f"Subject: {em['subject']}")
                print(f"Date: {em['date']}")
                print(f"Snippet: {em['snippet'][:120]}")
                print(f"ID: {em['id']}")
                print()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_calendar(args):
    """Show calendar events."""
    try:
        if args.days:
            events = get_all_upcoming_events(days=args.days)
        else:
            events = get_all_todays_events()
        if args.json:
            print(json.dumps(events, indent=2))
        else:
            for e in events:
                print(_format_event(e))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_calendar_check(args):
    """Verify all configured calendars are accessible."""
    try:
        results = check_calendars()
        for cal in results:
            label = cal.get("label") or "(primary)"
            status = cal["status"]
            count = cal["event_count"]
            print(f"  {label:12s}  {status}  ({count} events today)")
            print(f"               ID: {cal['id']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_backup(args):
    """Backup personal files to Google Drive."""
    from pa_google.drive import run_backup
    result = run_backup(keep=args.keep)
    print(f"Backup uploaded: {result['filename']}")
    if result.get("deleted"):
        print(f"Cleaned up {len(result['deleted'])} old backup(s)")


def main():
    parser = argparse.ArgumentParser(prog="pa-google", description="PA Google Workspace integration")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("briefing", help="Morning briefing (calendar + emails)")

    emails_p = sub.add_parser("emails", help="List emails")
    emails_p.add_argument("--unread", action="store_true", default=False, help="Only show unread emails")
    emails_p.add_argument("--limit", type=int, default=50)
    emails_p.add_argument("--json", action="store_true")

    cal_p = sub.add_parser("calendar", help="Show calendar events")
    cal_p.add_argument("--days", type=int, default=0, help="Show N days ahead (0 = today only)")
    cal_p.add_argument("--json", action="store_true")

    sub.add_parser("calendar-check", help="Verify all configured calendars are accessible")

    backup_p = sub.add_parser("backup", help="Backup personal files to Google Drive")
    backup_p.add_argument("--keep", type=int, default=7, help="Number of backups to keep")

    args = parser.parse_args()

    if args.command == "briefing":
        cmd_briefing(args)
    elif args.command == "emails":
        cmd_emails(args)
    elif args.command == "calendar":
        cmd_calendar(args)
    elif args.command == "calendar-check":
        cmd_calendar_check(args)
    elif args.command == "backup":
        cmd_backup(args)


if __name__ == "__main__":
    main()
