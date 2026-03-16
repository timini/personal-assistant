"""CLI entry point for pa-notion."""

import argparse
import json
import sys

from pa_notion.tasks import list_tasks, add_task, update_task, promote_task, sync_google_tasks


def cmd_tasks_list(args):
    """List tasks."""
    try:
        tasks = list_tasks(status_filter=args.status)
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
                print(f"  {status} {t['title']} {priority}{project}")
                if args.verbose:
                    print(f"    ID: {t['id']}")
                    print(f"    URL: {t['url']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tasks_add(args):
    """Add a task."""
    try:
        task = add_task(args.title, project=args.project or "", priority=args.priority or "", notes=args.notes or "")
        if args.json:
            print(json.dumps(task, indent=2))
        else:
            print(f"Created: {task['title']}")
            print(f"  ID: {task['id']}")
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


def cmd_tasks_sync(args):
    """Sync completed Google Tasks back to Notion."""
    try:
        synced = sync_google_tasks()
        if args.json:
            print(json.dumps(synced, indent=2))
        elif not synced:
            print("No completed Google Tasks to sync.")
        else:
            print(f"Synced {len(synced)} task(s) to Notion:")
            for s in synced:
                print(f"  Done: {s['title']} (from {s['list']} list)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_tasks_promote(args):
    """Promote a task to Google Tasks."""
    try:
        result = promote_task(args.id, list_name=args.tasklist, due=args.due)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            task = result["notion"]
            print(f"Promoted: {task['title']}")
            print(f"  Notion: {result['notion_url']}")
            print(f"  Google Tasks list: {args.tasklist}")
            if task.get("due_date") or args.due:
                print(f"  Due: {args.due or task['due_date']}")
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
    list_p.add_argument("--json", action="store_true")
    list_p.add_argument("--verbose", "-v", action="store_true")

    # tasks add
    add_p = tasks_sub.add_parser("add", help="Add a task")
    add_p.add_argument("title", help="Task title")
    add_p.add_argument("--project", help="Project name")
    add_p.add_argument("--priority", help="Priority level")
    add_p.add_argument("--notes", help="Notes (e.g. email link)")
    add_p.add_argument("--json", action="store_true")

    # tasks update
    update_p = tasks_sub.add_parser("update", help="Update a task")
    update_p.add_argument("id", help="Task ID")
    update_p.add_argument("--title", help="New title")
    update_p.add_argument("--status", help="New status")
    update_p.add_argument("--priority", help="New priority")
    update_p.add_argument("--project", help="New project")
    update_p.add_argument("--json", action="store_true")

    # tasks promote
    promote_p = tasks_sub.add_parser("promote", help="Promote task to Google Tasks")
    promote_p.add_argument("id", help="Notion task ID")
    promote_p.add_argument("--list", choices=["today", "next", "waiting"], default="today", dest="tasklist")
    promote_p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    promote_p.add_argument("--json", action="store_true")

    # tasks sync
    sync_p = tasks_sub.add_parser("sync", help="Sync completed Google Tasks back to Notion")
    sync_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "tasks":
        if args.action == "list":
            cmd_tasks_list(args)
        elif args.action == "add":
            cmd_tasks_add(args)
        elif args.action == "update":
            cmd_tasks_update(args)
        elif args.action == "promote":
            cmd_tasks_promote(args)
        elif args.action == "sync":
            cmd_tasks_sync(args)


if __name__ == "__main__":
    main()
