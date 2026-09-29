"""Task CRUD operations against the Notion tasks database."""

import re
import sys
from datetime import datetime, timedelta, timezone

from pa_core.cli_runner import run_gws
from pa_core.config import get_secret
from pa_notion.client import NotionClient


def _get_db_id() -> str:
    return get_secret("NOTION_TASKS_DB_ID")


def _extract_task(page: dict) -> dict:
    """Extract a flat task dict from a Notion page object."""
    props = page.get("properties", {})

    # Extract title
    title_prop = props.get("Name") or props.get("Task") or props.get("Title") or {}
    title_items = title_prop.get("title", [])
    title = title_items[0]["plain_text"] if title_items else "(untitled)"

    # Extract status
    status_prop = props.get("Status", {})
    status = ""
    if "status" in status_prop:
        status = status_prop["status"].get("name", "") if status_prop["status"] else ""
    elif "select" in status_prop:
        status = status_prop["select"].get("name", "") if status_prop["select"] else ""

    # Extract priority
    priority_prop = props.get("Priority", {})
    priority = ""
    if "select" in priority_prop:
        priority = priority_prop["select"].get("name", "") if priority_prop["select"] else ""

    # Extract project
    project_prop = props.get("Project", {})
    project = ""
    if "select" in project_prop:
        project = project_prop["select"].get("name", "") if project_prop["select"] else ""
    elif "relation" in project_prop:
        project = f"({len(project_prop['relation'])} linked)"

    # Extract due date
    due_prop = props.get("Due Date", {})
    due_date = ""
    if "date" in due_prop and due_prop["date"]:
        due_date = due_prop["date"].get("start", "")

    return {
        "id": page["id"],
        "title": title,
        "status": status,
        "priority": priority,
        "project": project,
        "due_date": due_date,
        "url": page.get("url", ""),
        "last_edited_time": page.get("last_edited_time", ""),
    }


def list_tasks(status_filter: str | None = None) -> list[dict]:
    """List tasks, optionally filtered by status."""
    client = NotionClient()
    db_id = _get_db_id()

    filter_body = None
    if status_filter:
        filter_body = {
            "property": "Status",
            "select": {"equals": status_filter},
        }

    pages = client.query_database(db_id, filter=filter_body)
    return [_extract_task(p) for p in pages]


def add_task(title: str, project: str = "", priority: str = "", notes: str = "") -> dict:
    """Add a new task to the tasks database. Verifies creation by re-fetching."""
    client = NotionClient()
    db_id = _get_db_id()

    properties: dict = {
        "Task": {"title": [{"text": {"content": title}}]},
    }
    if project:
        properties["Project"] = {"select": {"name": project}}
    if priority:
        properties["Priority"] = {"select": {"name": priority}}
    if notes:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    page = client.create_page(db_id, properties)
    created = _extract_task(page)

    # Verify by re-fetching
    verified = _extract_task(client.get_page(created["id"]))
    if not verified["title"]:
        raise RuntimeError(f"Task creation verification failed — page {created['id']} has no title")
    return verified


GOOGLE_TASK_LISTS = {
    "today": get_secret("GOOGLE_TODAY_TASKLIST_ID"),
}


def get_task(task_id: str) -> dict:
    """Fetch a single task by ID."""
    client = NotionClient()
    page = client.get_page(task_id)
    return _extract_task(page)


def promote_task(task_id: str, list_name: str = "today", due: str | None = None) -> dict:
    """Promote a Notion task to Google Tasks with a link back."""
    task = get_task(task_id)
    notion_url = f"https://www.notion.so/{task_id.replace('-', '')}"

    tasklist_id = GOOGLE_TASK_LISTS[list_name]

    title = task["title"]
    if task.get("project"):
        title = f"[{task['project']}] {title}"

    body: dict = {"title": title, "notes": notion_url}
    due_date = due or task.get("due_date")
    if due_date:
        body["due"] = f"{due_date}T00:00:00Z"

    result = run_gws("tasks", "tasks", "insert",
                     params={"tasklist": tasklist_id},
                     body=body)
    return {"notion": task, "google_task": result, "notion_url": notion_url}


def update_task(task_id: str, **updates) -> dict:
    """Update task properties. Accepts: title, status, priority, project, due_date.

    Verifies the update by re-fetching the page and checking the values match.
    Raises RuntimeError if verification fails.
    """
    client = NotionClient()
    properties: dict = {}

    if "title" in updates:
        properties["Name"] = {"title": [{"text": {"content": updates["title"]}}]}
    if "status" in updates:
        properties["Status"] = {"select": {"name": updates["status"]}}
    if "priority" in updates:
        properties["Priority"] = {"select": {"name": updates["priority"]}}
    if "project" in updates:
        properties["Project"] = {"select": {"name": updates["project"]}}
    if "due_date" in updates:
        properties["Due Date"] = {"date": {"start": updates["due_date"]}}
    if "notes" in updates:
        properties["Notes"] = {"rich_text": [{"text": {"content": updates["notes"]}}]}

    client.update_page(task_id, properties)

    # Verify by re-fetching
    verified = _extract_task(client.get_page(task_id))

    # Check each update was applied
    field_map = {"status": "status", "priority": "priority", "project": "project", "title": "title", "due_date": "due_date"}
    mismatches = []
    for key, field in field_map.items():
        if key in updates and verified[field] != updates[key]:
            mismatches.append(f"{key}: expected '{updates[key]}', got '{verified[field]}'")

    if mismatches:
        raise RuntimeError(f"Task update verification failed for {task_id}: {'; '.join(mismatches)}")

    if "status" in updates and updates["status"] == "Done":
        _complete_google_task(task_id)

    return verified


def _notion_id_from_url(url: str) -> str | None:
    """Extract Notion page ID from URL, re-inserting dashes."""
    match = re.search(r"notion\.so/(?:[^/]+-)?([a-f0-9]{32})$", url)
    if not match:
        return None
    hex_id = match.group(1)
    return f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}"


def _complete_google_task(notion_task_id: str) -> None:
    """Find and complete the Google Task linked to this Notion task ID."""
    notion_url_fragment = notion_task_id.replace("-", "")
    for _list_name, tasklist_id in GOOGLE_TASK_LISTS.items():
        try:
            tasks = run_gws("tasks", "tasks", "list",
                            params={"tasklist": tasklist_id})
            if not tasks or "items" not in tasks:
                continue
            for gt in tasks["items"]:
                notes = gt.get("notes", "")
                if notion_url_fragment in notes:
                    run_gws("tasks", "tasks", "patch",
                            params={"tasklist": tasklist_id, "task": gt["id"]},
                            body={"status": "completed"})
                    return
        except Exception as e:
            print(f"WARNING: Failed to complete Google Task for {notion_task_id}: {e}", file=sys.stderr)


def import_orphaned_tasks() -> list[dict]:
    """Import Google Tasks that don't have a Notion link into Notion.

    For incomplete orphans: create Notion task (To Do) → update Google Task notes with Notion URL.
    For completed orphans: create Notion task (Done) → delete Google Task.
    Returns list of imported tasks.
    """
    imported = []
    for list_name, tasklist_id in GOOGLE_TASK_LISTS.items():
        tasks = run_gws("tasks", "tasks", "list",
                        params={"tasklist": tasklist_id, "showCompleted": "true", "showHidden": "true"})
        if not tasks or "items" not in tasks:
            continue
        for gt in tasks["items"]:
            notes = gt.get("notes", "")
            # Skip tasks that already have a Notion link
            if _notion_id_from_url(notes):
                continue

            # Parse title — strip [Project] prefix if present
            raw_title = gt.get("title", "").strip()
            if not raw_title:
                continue

            project = ""
            title = raw_title
            project_match = re.match(r"^\[([^\]]+)\]\s*(.+)$", raw_title)
            if project_match:
                project = project_match.group(1)
                title = project_match.group(2)

            # Parse due date from Google Tasks format
            due_date = ""
            if gt.get("due"):
                due_date = gt["due"][:10]  # "2026-03-14T00:00:00.000Z" → "2026-03-14"

            is_completed = gt.get("status") == "completed"

            # Skip old completed orphans (>7 days) — not worth importing
            if is_completed:
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                completed_str = gt.get("completed", "")
                try:
                    completed_dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
                    if completed_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass  # can't parse date — proceed with import

            try:
                # Create in Notion
                notion_task = add_task(
                    title=title,
                    project=project,
                    priority="",  # no priority info in Google Tasks
                    notes=notes,  # preserve any existing notes
                )

                # If completed, mark Done immediately
                if is_completed:
                    update_task(notion_task["id"], status="Done")

                notion_url = f"https://www.notion.so/{notion_task['id'].replace('-', '')}"

                # Update Google Task with Notion link (marks it as managed)
                new_notes = notion_url
                if notes:
                    new_notes = f"{notion_url}\n{notes}"
                run_gws("tasks", "tasks", "patch",
                        params={"tasklist": tasklist_id, "task": gt["id"]},
                        body={"notes": new_notes})

                imported.append({
                    "title": title,
                    "notion_id": notion_task["id"],
                    "google_task_id": gt["id"],
                    "list": list_name,
                    "status": "Done" if is_completed else "To Do",
                    "project": project,
                })
            except Exception as e:
                print(f"ERROR importing '{title}': {e}", file=sys.stderr)
    return imported


def sync_google_tasks() -> list[dict]:
    """Sync Google Tasks with Notion.

    1. Import orphaned tasks (no Notion link) into Notion
    2. Sync completed tasks (with Notion link) back to Notion

    Returns list of all synced/imported tasks.
    """
    # Phase 1: Import orphaned tasks into Notion
    imported = import_orphaned_tasks()

    # Phase 2: Sync completed tasks with Notion links (existing logic)
    synced = []
    for list_name, tasklist_id in GOOGLE_TASK_LISTS.items():
        tasks = run_gws("tasks", "tasks", "list",
                        params={"tasklist": tasklist_id, "showCompleted": "true", "showHidden": "true"})
        if not tasks or "items" not in tasks:
            continue
        for gt in tasks["items"]:
            if gt.get("status") != "completed":
                continue
            notes = gt.get("notes", "")
            notion_id = _notion_id_from_url(notes)
            if not notion_id:
                continue
            try:
                # Check if already Done in Notion — skip, already synced
                existing = get_task(notion_id)
                if existing.get("status") == "Done":
                    continue

                notion_task = update_task(notion_id, status="Done")
                synced.append({
                    "title": notion_task["title"],
                    "notion_id": notion_id,
                    "google_task_id": gt["id"],
                    "list": list_name,
                })
            except Exception as e:
                print(f"ERROR syncing task {notion_id}: {e}", file=sys.stderr)
    return imported + synced
