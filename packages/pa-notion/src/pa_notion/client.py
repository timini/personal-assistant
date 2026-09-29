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
        """Query a Notion database and return all pages (handles pagination)."""
        body = {}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts

        all_results = []
        while True:
            result = self._request("POST", f"/databases/{database_id}/query", json=body)
            all_results.extend(result.get("results", []))
            if not result.get("has_more"):
                break
            body["start_cursor"] = result["next_cursor"]
        return all_results

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

    def create_page_in_page(self, parent_page_id: str, title: str, children: list[dict] | None = None) -> dict:
        """Create a child page under another page (not a database)."""
        body = {
            "parent": {"page_id": parent_page_id},
            "properties": {"title": [{"text": {"content": title}}]},
        }
        if children:
            body["children"] = children
        return self._request("POST", "/pages", json=body)

    def get_block_children(self, block_id: str) -> list[dict]:
        """Get child blocks of a page/block."""
        result = self._request("GET", f"/blocks/{block_id}/children")
        return result.get("results", [])

    def delete_block(self, block_id: str) -> dict:
        """Delete (archive) a block."""
        return self._request("DELETE", f"/blocks/{block_id}")

    def append_blocks(self, page_id: str, children: list[dict]) -> dict:
        """Append child blocks to a page."""
        return self._request("PATCH", f"/blocks/{page_id}/children", json={"children": children})
