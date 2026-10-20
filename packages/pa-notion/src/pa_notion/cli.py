"""CLI entry point for pa-notion."""

import argparse
import json
import sys

from pa_notion.tasks import (
    DuplicateTaskError,
    add_task,
    filter_tasks,
    get_task,
    get_task_body,
    list_tasks,
    update_task,
)
from pa_notion.heatmap import update_heatmap_page
from pa_notion.stats import get_task_stats, render_stats


def cmd_tasks_list(args):
    """List tasks."""
    try:
        tasks = filter_tasks(
            list_tasks(status_filter=args.status),
            open_only=args.open, search=args.search, project=args.project,
            lane=args.lane, due_before=args.due_before,
        )
        if args.json:
            print(json.dumps(tasks, indent=2))
        else:
            if not tasks:
                print("No tasks found.")
                return
            for t in tasks:
                status = f"[{t['status']}]" if t["status"] else ""
                priority = f"({t['priority']})" if t["priority"] else ""
                project = f"  #{t['project']}" if t["project"] else ""
                due = f"  due {t['due_date']}" if t.get("due_date") else ""
                print(f"  {status} {t['title']} {priority}{project}{due}")
                if args.verbose:
                    print(f"    ID: {t['id']}")
                    print(f"    URL: {t['url']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tasks_show(args):
    """Show one task with its notes and page body."""
    try:
        task = get_task(args.id)
        body = get_task_body(args.id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps({**task, "body": body}, indent=2))
        return
    print(task["title"])
    for label, key in (("Status", "status"), ("Priority", "priority"), ("Project", "project"),
                       ("Lane", "lane"), ("Due", "due_date"), ("ID", "id"), ("URL", "url")):
        if task.get(key):
            print(f"  {label}: {task[key]}")
    if task.get("notes"):
        print(f"\nNotes:\n{task['notes']}")
    if body:
        print(f"\nPage:\n{body}")


def cmd_tasks_add(args):
    """Add a task."""
    try:
        task = add_task(args.title, project=args.project or "", priority=args.priority or "",
                        notes=args.notes or "", force=args.force,
                        due_date=args.due or "", lane=args.lane or "")
        if args.json:
            print(json.dumps(task, indent=2))
        else:
            print(f"Created: {task['title']}")
            print(f"  ID: {task['id']}")
    except DuplicateTaskError as e:
        print(f"Not created. {e}", file=sys.stderr)
        print("Update the existing task instead, or pass --force if it really is separate.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tasks_update(args):
    """Update a task."""
    updates = {}
    if args.title:
        updates["title"] = args.title
    if args.status:
        updates["status"] = args.status
    if args.priority:
        updates["priority"] = args.priority
    if args.project:
        updates["project"] = args.project
    if args.lane:
        updates["lane"] = args.lane
    if args.due:
        updates["due_date"] = None if args.due.lower() == "none" else args.due
    if args.notes:
        updates["notes"] = args.notes
    if args.append_notes:
        updates["append_notes"] = args.append_notes

    if not updates:
        print("No updates specified.", file=sys.stderr)
        sys.exit(1)

    try:
        task = update_task(args.id, **updates)
        if args.json:
            print(json.dumps(task, indent=2))
        else:
            print(f"Updated: {task['title']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_heatmap(args):
    """Generate achievement heatmap on Notion."""
    try:
        url = update_heatmap_page(page_id=args.page, weeks=args.weeks)
        print(f"Heatmap updated: {url}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args):
    """Show task stats with ASCII bar charts."""
    try:
        stats = get_task_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(render_stats(stats))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="pa-notion", description="PA Notion integration")
    sub = parser.add_subparsers(dest="command", required=True)

    # tasks subcommand group
    tasks_parser = sub.add_parser("tasks", help="Manage tasks")
    tasks_sub = tasks_parser.add_subparsers(dest="action", required=True)

    # tasks list
    list_p = tasks_sub.add_parser("list", help="List tasks")
    list_p.add_argument("--status", help="Filter by status")
    list_p.add_argument("--open", action="store_true", help="Exclude Done and Discarded")
    list_p.add_argument("--search", help="Text to find in the title or notes")
    list_p.add_argument("--project", help="Project name contains this text")
    list_p.add_argument("--lane", help="Lane contains this text, e.g. Live")
    list_p.add_argument("--due-before", help="Due on or before YYYY-MM-DD")
    list_p.add_argument("--json", action="store_true")
    list_p.add_argument("--verbose", "-v", action="store_true")

    # tasks show
    show_p = tasks_sub.add_parser("show", help="Show one task with notes and page body")
    show_p.add_argument("id", help="Task ID")
    show_p.add_argument("--json", action="store_true")

    # tasks add
    add_p = tasks_sub.add_parser("add", help="Add a task")
    add_p.add_argument("title", help="Task title")
    add_p.add_argument("--project", help="Project name")
    add_p.add_argument("--priority", help="Priority level")
    add_p.add_argument("--notes", help="Notes (e.g. email link)")
    add_p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    add_p.add_argument("--lane", help="Lane, e.g. '🔥 Live'")
    add_p.add_argument("--force", action="store_true", help="Create even if a similar open task exists")
    add_p.add_argument("--json", action="store_true")

    # tasks update
    update_p = tasks_sub.add_parser("update", help="Update a task")
    update_p.add_argument("id", help="Task ID")
    update_p.add_argument("--title", help="New title")
    update_p.add_argument("--status", help="New status")
    update_p.add_argument("--priority", help="New priority")
    update_p.add_argument("--project", help="New project")
    update_p.add_argument("--lane", help="New lane, e.g. '🅿️ Parked'")
    update_p.add_argument("--due", help="Due date (YYYY-MM-DD), or 'none' to clear it")
    notes_g = update_p.add_mutually_exclusive_group()
    notes_g.add_argument("--notes", help="Replace the notes")
    notes_g.add_argument("--append-notes", help="Add a paragraph to the end of the notes")
    update_p.add_argument("--json", action="store_true")


    # stats subcommand
    stats_p = sub.add_parser("stats", help="Task stats with ASCII bar charts")
    stats_p.add_argument("--json", action="store_true", help="Output as JSON")

    # heatmap subcommand
    heatmap_p = sub.add_parser("heatmap", help="GitHub-style activity heatmap on Notion")
    heatmap_p.add_argument("--weeks", type=int, default=12, help="Number of weeks to show (default: 12)")
    heatmap_p.add_argument("--page", help="Notion page ID to write to")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "heatmap":
        cmd_heatmap(args)
    elif args.command == "tasks":
        if args.action == "list":
            cmd_tasks_list(args)
        elif args.action == "show":
            cmd_tasks_show(args)
        elif args.action == "add":
            cmd_tasks_add(args)
        elif args.action == "update":
            cmd_tasks_update(args)


if __name__ == "__main__":
    main()
