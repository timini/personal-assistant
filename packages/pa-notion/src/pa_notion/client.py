"""Notion API client using httpx."""

import httpx

from pa_core.config import get_secret

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Thin wrapper around the Notion API."""

    def __init__(self):
        self.token = get_secret("NOTION_ACCESS_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{NOTION_API_BASE}{path}"
        with httpx.Client(timeout=30) as client:
            resp = client.request(method, url, headers=self.headers, **kwargs)
            resp.raise_for_status()
            return resp.json()

    def query_database(self, database_id: str, filter: dict | None = None, sorts: list | None = None) -> list[dict]:
        """Query a Notion database and return pages."""
        body = {}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        result = self._request("POST", f"/databases/{database_id}/query", json=body)
        return result.get("results", [])

    def create_page(self, parent_id: str, properties: dict) -> dict:
        """Create a page in a database."""
        body = {
            "parent": {"database_id": parent_id},
            "properties": properties,
        }
        return self._request("POST", "/pages", json=body)

    def update_page(self, page_id: str, properties: dict) -> dict:
        """Update a page's properties."""
        return self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def get_page(self, page_id: str) -> dict:
        """Get a page by ID."""
        return self._request("GET", f"/pages/{page_id}")
