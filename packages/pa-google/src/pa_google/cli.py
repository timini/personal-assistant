"""CLI entry point for pa-google."""

import argparse
import json
import sys

from pa_google.gmail import archive_email, create_draft, get_inbox_emails, read_email
from pa_google.calendar import (
    add_event,
    check_calendars,
    delete_event,
    get_all_todays_events,
    get_all_upcoming_events,
    get_event,
    update_event,
)
from pa_core.config import get_now
from pa_core.state import get_state, set_state

_TRIAGE_STATE_KEY = "last_email_triage"


def _format_event(e: dict) -> str:
    """Format event for display with optional calendar label."""
    time_str = e["start"].split("T")[1][:5] if "T" in e["start"] else e["start"]
    label = e.get("calendar")
    label_str = f" [{label}]" if label else ""
    id_str = f"  (id {e['id']})" if e.get("id") else ""
    return f"  {time_str}{label_str}  {e['summary']}{id_str}"


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
    """List inbox emails (optionally only those since the last triage)."""
    # --mark-triaged: stamp 'now' as the triage cursor and exit (no fetch).
    if getattr(args, "mark_triaged", False):
        now = get_now()
        set_state(_TRIAGE_STATE_KEY, {"epoch": now["epoch"], "display": now["display"]})
        print(f"Marked triaged at {now['display']}")
        return

    after = None
    if getattr(args, "since_last", False):
        last = get_state(_TRIAGE_STATE_KEY)
        if last:
            after = last["epoch"]
            print(f"Showing emails since last triage ({last['display']})\n")
        else:
            print("No previous triage recorded — showing full inbox\n")

    try:
        emails = get_inbox_emails(limit=args.limit, unread_only=args.unread, after=after, query=args.query)
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


def cmd_read(args):
    """Print one email in full: headers, body text and attachments."""
    try:
        email = read_email(args.id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(email, indent=2))
        return
    for label, key in (("From", "from"), ("To", "to"), ("Subject", "subject"), ("Date", "date"),
                       ("Thread", "thread_id"), ("Link", "link")):
        print(f"{label}: {email[key]}")
    for a in email["attachments"]:
        print(f"Attachment: {a['filename']} ({a['mime_type']}, id {a['attachment_id']})")
    print()
    print(email["body"])


def cmd_archive(args):
    """Archive whole threads by message id."""
    failed = []
    for message_id in args.ids:
        try:
            archive_email(message_id)
        except Exception as e:
            failed.append(message_id)
            print(f"Failed {message_id}: {e}", file=sys.stderr)
    print(f"Archived {len(args.ids) - len(failed)} of {len(args.ids)}")
    if failed:
        sys.exit(1)


def cmd_draft(args):
    """Create a Gmail draft for review. Never sends."""
    body = open(args.body_file).read() if args.body_file else args.body
    if not body:
        print("Error: give --body or --body-file", file=sys.stderr)
        sys.exit(1)
    try:
        result = create_draft(to=args.to, subject=args.subject, body=body, thread_id=args.thread)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Draft created: {result['link']}")


def _print_event(event: dict, verb: str, as_json: bool):
    if as_json:
        print(json.dumps(event, indent=2))
        return
    print(f"{verb}: {event['summary']}  {event['start']} to {event['end']}")
    print(f"  ID: {event['id']}  Calendar: {event['calendar_id']}")
    if event.get("link"):
        print(f"  Link: {event['link']}")


def cmd_event(args):
    """Add, show, update or delete one calendar event."""
    try:
        if args.action == "add":
            event = add_event(args.title, args.start, args.end, calendar=args.calendar,
                              location=args.location or "", description=args.description or "",
                              attendees=args.attendee)
            _print_event(event, "Created", args.json)
        elif args.action == "show":
            _print_event(get_event(args.id, calendar=args.calendar), "Event", args.json)
        elif args.action == "update":
            event = update_event(args.id, calendar=args.calendar, title=args.title, start=args.start,
                                 end=args.end, location=args.location, description=args.description)
            _print_event(event, "Updated", args.json)
        elif args.action == "delete":
            delete_event(args.id, calendar=args.calendar)
            print(f"Deleted {args.id}")
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
    emails_p.add_argument("--since-last", action="store_true", default=False,
                          help="Only show emails received since the last triage was marked done")
    emails_p.add_argument("--mark-triaged", action="store_true", default=False,
                          help="Record 'now' as the last-triaged time (run at the end of a triage pass)")
    emails_p.add_argument("--query", help="Gmail search instead of the inbox, e.g. 'from:x in:all'")
    emails_p.add_argument("--limit", type=int, default=50)
    emails_p.add_argument("--json", action="store_true")

    read_p = sub.add_parser("read", help="Show one email in full (body, attachments, thread id)")
    read_p.add_argument("id", help="Message id")
    read_p.add_argument("--json", action="store_true")

    archive_p = sub.add_parser("archive", help="Archive the threads of one or more messages")
    archive_p.add_argument("ids", nargs="+", help="Message ids")

    draft_p = sub.add_parser("draft", help="Create a Gmail draft for review (never sends)")
    draft_p.add_argument("--to", required=True)
    draft_p.add_argument("--subject", required=True)
    draft_p.add_argument("--body", help="Body text")
    draft_p.add_argument("--body-file", help="Read the body from this file")
    draft_p.add_argument("--thread", help="Thread id, to reply in that conversation")

    event_p = sub.add_parser("event", help="Add, show, update or delete a calendar event")
    event_sub = event_p.add_subparsers(dest="action", required=True)
    ev_add = event_sub.add_parser("add", help="Create an event (Google assigns the id)")
    ev_add.add_argument("title")
    ev_add.add_argument("--start", required=True, help="YYYY-MM-DD (all day) or YYYY-MM-DDTHH:MM")
    ev_add.add_argument("--end", help="Defaults to one hour later, or the next day for all-day events")
    ev_add.add_argument("--attendee", action="append", help="Invite this email; repeat for more")
    ev_show = event_sub.add_parser("show", help="Show one event")
    ev_show.add_argument("id")
    ev_update = event_sub.add_parser("update", help="Change only the given fields")
    ev_update.add_argument("id")
    ev_update.add_argument("--title")
    ev_update.add_argument("--start")
    ev_update.add_argument("--end")
    ev_delete = event_sub.add_parser("delete", help="Delete an event")
    ev_delete.add_argument("id")
    for p in (ev_add, ev_show, ev_update, ev_delete):
        p.add_argument("--calendar", help="Calendar label from user.yaml, or a calendar id (default primary)")
    for p in (ev_add, ev_update):
        p.add_argument("--location")
        p.add_argument("--description")
    for p in (ev_add, ev_show, ev_update):
        p.add_argument("--json", action="store_true")

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
    elif args.command == "read":
        cmd_read(args)
    elif args.command == "archive":
        cmd_archive(args)
    elif args.command == "draft":
        cmd_draft(args)
    elif args.command == "event":
        cmd_event(args)
    elif args.command == "calendar-check":
        cmd_calendar_check(args)
    elif args.command == "backup":
        cmd_backup(args)


if __name__ == "__main__":
    main()
