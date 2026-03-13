"""Task CRUD operations against the Notion tasks database."""

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
    """Add a new task to the tasks database."""
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
    return _extract_task(page)


def update_task(task_id: str, **updates) -> dict:
    """Update task properties. Accepts: title, status, priority, project."""
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

    page = client.update_page(task_id, properties)
    return _extract_task(page)
