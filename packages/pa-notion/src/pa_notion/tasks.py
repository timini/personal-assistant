"""Task CRUD operations against the Notion tasks database."""

import difflib
import re

from pa_core.config import get_secret
from pa_notion.client import NotionClient


# Notion rejects rich_text segments longer than this.
RICH_TEXT_LIMIT = 2000

# Title similarity at or above this counts as the same task.
DUPLICATE_RATIO = 0.85

_FILLER = {"a", "an", "the", "to", "for", "of", "and", "re", "my"}


class DuplicateTaskError(Exception):
    """An open task already covers this. Update it instead of adding another."""

    def __init__(self, title: str, matches: list[dict]):
        self.matches = matches
        listed = "; ".join(f"{m['title']} ({m['id']})" for m in matches)
        super().__init__(f"Similar open task exists for {title!r}: {listed}")


def _get_db_id() -> str:
    return get_secret("NOTION_TASKS_DB_ID")


def _rich_text(text: str) -> list[dict]:
    """Split text into segments Notion will accept."""
    return [
        {"text": {"content": text[i:i + RICH_TEXT_LIMIT]}}
        for i in range(0, max(len(text), 1), RICH_TEXT_LIMIT)
    ]


def _normalise(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in _FILLER)


def find_similar_tasks(title: str, tasks: list[dict]) -> list[dict]:
    """Open tasks whose titles are near-identical to `title`."""
    target = _normalise(title)
    matches = []
    for task in tasks:
        if task.get("status") in ("Done", "Discarded"):
            continue
        other = _normalise(task.get("title", ""))
        if other and difflib.SequenceMatcher(None, target, other).ratio() >= DUPLICATE_RATIO:
            matches.append(task)
    return matches


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

    # Extract lane (🔥 Live / 🅿️ Parked / 💤 Someday). Consumers rank and filter
    # on this, so it must always be present — a missing key would KeyError, and
    # an absent lane must not read as "not Parked".
    lane_prop = props.get("Lane", {})
    lane = ""
    if lane_prop.get("select"):
        lane = lane_prop["select"].get("name", "")

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

    notes = "".join(seg.get("plain_text", "") for seg in props.get("Notes", {}).get("rich_text", []))

    return {
        "id": page["id"],
        "title": title,
        "status": status,
        "priority": priority,
        "lane": lane,
        "project": project,
        "due_date": due_date,
        "notes": notes,
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


def filter_tasks(
    tasks: list[dict],
    *,
    open_only: bool = False,
    search: str | None = None,
    project: str | None = None,
    lane: str | None = None,
    due_before: str | None = None,
) -> list[dict]:
    """Filter task dicts locally. Text matches are case-insensitive substrings."""
    def has(value: str, needle: str | None) -> bool:
        return needle is None or needle.lower() in (value or "").lower()

    return [
        t for t in tasks
        if not (open_only and t.get("status") in ("Done", "Discarded"))
        and (search is None or has(t.get("title", ""), search) or has(t.get("notes", ""), search))
        and has(t.get("project", ""), project)
        and has(t.get("lane", ""), lane)
        and (due_before is None or (t.get("due_date") and t["due_date"][:10] <= due_before))
    ]


def add_task(
    title: str,
    project: str = "",
    priority: str = "",
    notes: str = "",
    status: str = "To Do",
    force: bool = False,
    due_date: str = "",
    lane: str = "",
) -> dict:
    """Add a new task to the tasks database. Verifies creation by re-fetching.

    Refuses when a near-identical open task exists (DuplicateTaskError), unless
    `force` is set: the usual right move is to update the existing task.
    """
    if not force:
        matches = find_similar_tasks(title, list_tasks())
        if matches:
            raise DuplicateTaskError(title, matches)
    client = NotionClient()
    db_id = _get_db_id()

    properties: dict = {
        "Task": {"title": [{"text": {"content": title}}]},
        "Status": {"select": {"name": status}},
    }
    if project:
        properties["Project"] = {"select": {"name": project}}
    if priority:
        properties["Priority"] = {"select": {"name": priority}}
    if notes:
        properties["Notes"] = {"rich_text": _rich_text(notes)}
    if due_date:
        properties["Due Date"] = {"date": {"start": due_date}}
    if lane:
        properties["Lane"] = {"select": {"name": lane}}

    page = client.create_page(db_id, properties)
    created = _extract_task(page)

    # Verify by re-fetching
    verified = _extract_task(client.get_page(created["id"]))
    if not verified["title"]:
        raise RuntimeError(f"Task creation verification failed — page {created['id']} has no title")
    return verified


def get_task(task_id: str) -> dict:
    """Fetch a single task by ID."""
    client = NotionClient()
    page = client.get_page(task_id)
    return _extract_task(page)


def get_task_body(task_id: str) -> str:
    """Plain text of the blocks on a task page, one line per block."""
    lines = []
    for block in NotionClient().get_block_children(task_id):
        content = block.get(block.get("type", ""), {})
        text = "".join(seg.get("plain_text", "") for seg in content.get("rich_text", []))
        if block.get("type") in ("bulleted_list_item", "numbered_list_item", "to_do"):
            text = f"- {text}"
        if text:
            lines.append(text)
    return "\n".join(lines)


def update_task(task_id: str, **updates) -> dict:
    """Update task properties. Accepts: title, status, priority, project, lane,
    due_date (None clears it), notes (replaces) and append_notes (adds a paragraph).

    Verifies the update by re-fetching the page and checking the values match.
    Raises RuntimeError if verification fails.
    """
    client = NotionClient()
    properties: dict = {}

    if "title" in updates:
        properties["Task"] = {"title": [{"text": {"content": updates["title"]}}]}
    if "status" in updates:
        properties["Status"] = {"select": {"name": updates["status"]}}
    if "priority" in updates:
        properties["Priority"] = {"select": {"name": updates["priority"]}}
    if "project" in updates:
        properties["Project"] = {"select": {"name": updates["project"]}}
    if "lane" in updates:
        properties["Lane"] = {"select": {"name": updates["lane"]}}
    if "due_date" in updates:
        due = updates["due_date"]
        properties["Due Date"] = {"date": {"start": due} if due else None}
    if "notes" in updates:
        properties["Notes"] = {"rich_text": _rich_text(updates["notes"])}
    if "append_notes" in updates:
        existing = _extract_task(client.get_page(task_id))["notes"]
        combined = f"{existing}\n\n{updates['append_notes']}" if existing else updates["append_notes"]
        properties["Notes"] = {"rich_text": _rich_text(combined)}

    client.update_page(task_id, properties)

    # Verify by re-fetching
    verified = _extract_task(client.get_page(task_id))

    # Check each update was applied
    field_map = {"status": "status", "priority": "priority", "project": "project", "title": "title",
                 "due_date": "due_date", "lane": "lane"}
    mismatches = []
    for key, field in field_map.items():
        if key in updates and verified[field] != (updates[key] or ""):
            mismatches.append(f"{key}: expected '{updates[key]}', got '{verified[field]}'")

    if mismatches:
        raise RuntimeError(f"Task update verification failed for {task_id}: {'; '.join(mismatches)}")

    return verified
