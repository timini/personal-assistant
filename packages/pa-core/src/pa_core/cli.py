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


def cmd_context(args):
    from pa_core.context import get_today_context, render_context
    import json
    ctx = get_today_context()
    if args.json:
        print(json.dumps(ctx, indent=2, default=str))
    else:
        print(render_context(ctx))


def cmd_checkin(args):
    """Single command to start a daily session: sync, backup, context, coaching prompt."""
    import json

    print("Starting daily check-in...\n", file=sys.stderr)

    # 1. Sync Google Tasks → Notion
    print("Syncing Google Tasks...", file=sys.stderr)
    synced = []
    try:
        from pa_notion.tasks import sync_google_tasks
        from pa_core.daily_log import log_event
        synced = sync_google_tasks()
        for s in synced:
            if s.get("status") == "To Do":
                log_event("task", "created", f"Imported from Google Tasks: {s['title']}")
            else:
                log_event("task", "completed", f"Completed: {s['title']} (synced from Google Tasks)")
        if synced:
            imported = [s for s in synced if s.get("status") == "To Do"]
            completed = [s for s in synced if s.get("status") != "To Do"]
            parts = []
            if completed:
                parts.append(f"synced {len(completed)} completed")
            if imported:
                parts.append(f"imported {len(imported)} new")
            print(f"  Google Tasks: {', '.join(parts)}.", file=sys.stderr)
        else:
            print("  No tasks to sync.", file=sys.stderr)
    except Exception as exc:
        print(f"  Task sync failed: {exc}", file=sys.stderr)

    # 2. Backup personal files to Google Drive
    if not args.no_backup:
        print("Backing up to Google Drive...", file=sys.stderr)
        try:
            from pa_google.drive import run_backup
            result = run_backup()
            print(f"  Backup uploaded: {result['filename']}", file=sys.stderr)
        except Exception as exc:
            print(f"  Backup failed: {exc}", file=sys.stderr)

    # 3. Fetch full context
    print("Fetching today's context...", file=sys.stderr)
    from pa_core.context import get_today_context, render_context
    ctx = get_today_context()

    print("", file=sys.stderr)  # blank line separator

    # 4. Output context + coaching instructions for Claude
    if args.json:
        print(json.dumps(ctx, indent=2, default=str))
    else:
        print(render_context(ctx))

    # 5. Append coaching prompt
    if not args.json:
        period = ctx["now"]["period"]
        name = ctx["now"].get("display", "today")
        if period == "evening" or args.evening:
            print("\n---\n")
            print("## Evening Session")
            print("Follow the evening session instructions: habit check-in, freeform wins,")
            print("gratitude, tomorrow preview. Then generate and send the evening briefing.")
        else:
            print("\n---\n")
            print("## Morning Session")
            print("Start with the wellness check-in (mood 1-5, physical A-D).")
            print("Then present tasks matched to energy level — max 5, curated, not a dump.")
            print("Frame the day as winnable: \"Here's what would make today a win.\"")
            print("Check user-instructions.md for personal context and contacts.")


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

    # checkin
    ci = sub.add_parser("checkin", help="Start daily session: sync tasks, backup, fetch context, coaching prompt")
    ci.add_argument("--evening", action="store_true", help="Run as evening session")
    ci.add_argument("--no-backup", action="store_true", help="Skip Google Drive backup")
    ci.add_argument("--json", action="store_true", help="Output context as JSON (no coaching prompt)")

    # context
    cp = sub.add_parser("context", help="Today's full context (calendar + emails + tasks + habits + weather)")
    cp.add_argument("--json", action="store_true", help="Output as JSON")

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
    elif args.command == "checkin":
        cmd_checkin(args)
    elif args.command == "context":
        cmd_context(args)
    elif args.command == "log":
        cmd_log(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
