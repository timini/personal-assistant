"""PA Core CLI: setup, checkin, context, briefing, memory, logging and reports."""

import argparse
import json
import sys


def cmd_setup(args):
    from pa_core.setup import setup
    setup()


def cmd_briefing(args):
    if args.evening:
        from pa_core.briefing import generate_evening_briefing, save_evening_briefing
        if args.save:
            print(f"Saved to {save_evening_briefing(date=args.date)}")
        else:
            print(generate_evening_briefing(date=args.date))
    else:
        from pa_core.briefing import generate_briefing, save_briefing
        if args.save:
            print(f"Saved to {save_briefing(date=args.date)}")
        else:
            print(generate_briefing(date=args.date))
    if not args.no_backup:
        _backup()


def _backup(stream=None):
    try:
        from pa_google.drive import run_backup
        result = run_backup()
        print(f"Backup uploaded: {result['filename']}", file=stream or sys.stdout)
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)


def cmd_context(args):

    from pa_core.context import get_today_context, render_context

    ctx = get_today_context()
    if args.json:
        print(json.dumps(ctx, indent=2, default=str))
    else:
        print(render_context(ctx))


def _open_tasks() -> list[dict]:
    try:
        from pa_notion.tasks import list_tasks
        return [t for t in list_tasks() if t.get("status") not in ("Done", "Discarded")]
    except Exception as exc:
        print(f"  Tasks unavailable: {exc}", file=sys.stderr)
        return []


def cmd_checkin(args):
    """Start a session: context, memory brief, then the morning or evening prompt."""

    from pa_core.context import get_today_context, render_context
    from pa_core.memory import render_brief

    print("Fetching today's context...", file=sys.stderr)
    ctx = get_today_context()
    if args.json:
        print(json.dumps(ctx, indent=2, default=str))
        return

    print(render_context(ctx))
    brief = render_brief(today=ctx["now"].get("date"))
    if brief:
        print("\n---\n")
        print(brief)

    print("\n---\n")
    if args.evening or ctx["now"]["period"] == "evening":
        from pa_core.config import get_user_config
        from pa_core.daily_log import get_events
        from pa_core.prompts import build_evening_prompt

        today = ctx["now"].get("date")
        print("## Evening session\n")
        print(build_evening_prompt(
            habits=get_user_config().get("habits", []),
            events=get_events(today) if today else [],
            today=today,
            tomorrow_tasks=_open_tasks()[:3],
        ))
    else:
        from pa_core.prompts import build_morning_prompt

        print("## Morning session\n")
        print(build_morning_prompt(
            schedule=ctx.get("calendar", []),
            tasks=_open_tasks(),
            today=ctx["now"].get("date"),
            health=ctx.get("health"),
        ))

    if not args.no_backup:
        _backup(stream=sys.stderr)


def cmd_memory(args):
    from pa_core import memory

    try:
        if args.memory_command == "brief":
            print(memory.render_brief() or "Memory is empty.")
        elif args.memory_command == "add":
            tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
            entry = memory.add(args.type, args.name, args.summary, body=args.body,
                               tags=tags, due=args.due, source=args.source)
            print(f"Saved {entry['type']} {entry['name']}")
        elif args.memory_command == "show":
            entry = memory.get(args.name)
            if entry is None:
                raise KeyError(f"No memory entry named {args.name!r}")
            print(f"{entry['name']} ({entry['type']}, updated {entry.get('updated')})")
            print(entry["summary"])
            if entry.get("due"):
                print(f"Due: {entry['due']}")
            if entry.get("body"):
                print(f"\n{entry['body']}")
        elif args.memory_command == "search":
            results = memory.search(" ".join(args.query), limit=args.limit)
            for r in results:
                print(f"[{r['type']}] {r['name']}: {r['summary']}")
            if not results:
                print("No matches.")
        elif args.memory_command == "list":
            for e in memory.list_entries(args.type):
                due = f" (due {e['due']})" if e.get("due") else ""
                print(f"[{e['type']}] {e['name']}: {e['summary']}{due}")
        elif args.memory_command == "done":
            memory.close_loop(args.name, " ".join(args.outcome))
            print(f"Closed {args.name}")
        elif args.memory_command == "archive":
            memory.archive(args.name, " ".join(args.reason))
            print(f"Archived {args.name}")
        elif args.memory_command == "journal":
            print(memory.journal(" ".join(args.text)))
        elif args.memory_command == "lint":
            issues = memory.lint()
            print("\n".join(issues) if issues else "No issues.")
        elif args.memory_command == "import-claude":
            from pathlib import Path
            print(f"Imported {memory.import_claude_memory(Path(args.path))} entries")
    except (KeyError, ValueError) as exc:
        print(str(exc).strip("'\""), file=sys.stderr)
        raise SystemExit(1)


def cmd_now(args):
    from pa_core.config import get_now
    print(json.dumps(get_now(), indent=2, default=str))


def cmd_log(args):
    from pa_core.daily_log import log_event
    links = {}
    for item in args.link or []:
        label, sep, url = item.partition("=")
        if not sep:
            print(f"--link must be label=url, got {item!r}", file=sys.stderr)
            raise SystemExit(1)
        links[label] = url
    event = log_event(
        category=args.category,
        action=args.action,
        summary=args.summary,
        project=args.project,
        details=json.loads(args.details) if args.details else None,
        links=links or None,
    )
    print(f"Logged: [{event['category']}] {event['action']} — {event['summary']}")


def cmd_report(args):
    """Generate a deterministic HTML report and optionally deliver it."""
    from pathlib import Path
    from pa_core.report import deliver_report, generate_report

    bundle = generate_report(
        kind=args.kind,
        date=args.date,
        input_path=Path(args.input) if args.input else None,
        insights=not args.no_insights,
    )
    print(f"HTML report: {bundle.html_path}")
    if args.deliver and not args.dry_run:
        results = deliver_report(bundle)
        drive = results.get("drive", {})
        if drive.get("ok"):
            print(f"Published: {drive['url']}")
        for channel in ("email",):
            result = results.get(channel, {})
            print(f"{channel.title()}: {'sent' if result.get('ok') else 'failed — ' + result.get('error', 'unknown error')}")
        if any(not result.get("ok") for result in results.values()):
            raise SystemExit(1)


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
    bp.add_argument("--no-backup", action="store_true", help="Skip Google Drive backup")

    # checkin
    ci = sub.add_parser("checkin", help="Start a session: context, memory brief, morning/evening prompt")
    ci.add_argument("--evening", action="store_true", help="Run as evening session")
    ci.add_argument("--no-backup", action="store_true", help="Skip Google Drive backup")
    ci.add_argument("--json", action="store_true", help="Output context as JSON only")

    # context
    cp = sub.add_parser("context", help="Today's full context (calendar + emails + tasks + habits + weather)")
    cp.add_argument("--json", action="store_true", help="Output as JSON")

    # memory
    mp = sub.add_parser("memory", help="Shared assistant memory: brief, add, search, loops, journal")
    msub = mp.add_subparsers(dest="memory_command", required=True)
    msub.add_parser("brief", help="Session-start brief: due loops, rules, lessons, people, journal")
    ma = msub.add_parser("add", help="Create or update an entry")
    ma.add_argument("type", choices=("preference", "lesson", "person", "fact", "project", "loop"))
    ma.add_argument("name", help="Short name; becomes the entry's slug")
    ma.add_argument("summary", help="One-line summary shown in the brief")
    ma.add_argument("--body", default=None, help="Longer detail")
    ma.add_argument("--tags", default=None, help="Comma-separated tags")
    ma.add_argument("--due", default=None, help="Loops: next check date YYYY-MM-DD")
    ma.add_argument("--source", default=None, help="Where this came from (email link, conversation)")
    ms = msub.add_parser("show", help="Show one entry in full")
    ms.add_argument("name")
    mq = msub.add_parser("search", help="Search entries and the journal")
    mq.add_argument("query", nargs="+")
    mq.add_argument("--limit", type=int, default=10)
    ml = msub.add_parser("list", help="List active entries")
    ml.add_argument("--type", default=None)
    md = msub.add_parser("done", help="Close a loop with its outcome")
    md.add_argument("name")
    md.add_argument("outcome", nargs="+")
    mr = msub.add_parser("archive", help="Retire an entry that is wrong or superseded")
    mr.add_argument("name")
    mr.add_argument("reason", nargs="+")
    mj = msub.add_parser("journal", help="Append a dated note of what happened")
    mj.add_argument("text", nargs="+")
    msub.add_parser("lint", help="Find stale loops and near-duplicate entries")
    mi = msub.add_parser("import-claude", help="Import a Claude Code memory directory")
    mi.add_argument("path")

    # log
    lp = sub.add_parser("log", help="Log an event to today's daily log")
    from pa_core.daily_log import CATEGORIES
    lp.add_argument("category", choices=sorted(CATEGORIES), help="Event category")
    lp.add_argument("action", help="Action: archived, created, completed, surfaced, flagged, etc.")
    lp.add_argument("summary", help="Short description of the event")
    lp.add_argument("--project", default=None, help="Associated project name")
    lp.add_argument("--details", default=None, help="Extra structured data as a JSON object")
    lp.add_argument("--link", action="append", help="label=url for a resource; repeat for more")

    # now
    sub.add_parser("now", help="Current date and time in the user's time zone, as JSON")

    # report
    rp = sub.add_parser("report", help="Generate a deterministic HTML report")
    rp.add_argument("--kind", choices=("daily", "health", "tasks", "research"), default="daily")
    rp.add_argument("--date", default=None, help="Report date (YYYY-MM-DD), defaults to today")
    rp.add_argument("--input", default=None, help="Structured JSON input for a research report")
    rp.add_argument("--no-insights", action="store_true", help="Skip optional Claude insights")
    rp.add_argument("--deliver", action="store_true", help="Publish to Drive and send by email")
    rp.add_argument("--dry-run", action="store_true", help="Generate locally without external delivery")

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
    elif args.command == "now":
        cmd_now(args)
    elif args.command == "memory":
        cmd_memory(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
