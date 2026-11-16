"""Tests for add_task — ensures Status is set on creation."""

from unittest.mock import patch, MagicMock

from pa_notion.tasks import add_task


class TestAddTaskDefaults:
    """add_task must set Status so Notion doesn't grey out the new task."""

    @patch("pa_notion.tasks.NotionClient")
    @patch("pa_notion.tasks._get_db_id", return_value="db-123")
    def test_default_status_is_to_do(self, _db, MockClient):
        client = MockClient.return_value
        client.create_page.return_value = {
            "id": "task-1",
            "properties": {
                "Task": {"title": [{"plain_text": "Test", "text": {"content": "Test"}}]},
                "Status": {"select": {"name": "To Do"}},
                "Priority": {"select": None}, "Project": {"select": None},
                "Due Date": {"date": None}, "Notes": {"rich_text": []},
                "Parent item": {"relation": []},
            },
            "url": "https://notion.so/task-1",
        }
        client.get_page.return_value = client.create_page.return_value

        add_task("Test")

        # Verify create_page was called with Status set
        _, kwargs_or_props = client.create_page.call_args[0][0], client.create_page.call_args[0][1]
        props = client.create_page.call_args[0][1]
        assert "Status" in props, "Status property must be set on creation"
        assert props["Status"] == {"select": {"name": "To Do"}}, \
            f"Default Status should be To Do, got {props['Status']!r}"

    @patch("pa_notion.tasks.NotionClient")
    @patch("pa_notion.tasks._get_db_id", return_value="db-123")
    def test_explicit_status_overrides_default(self, _db, MockClient):
        client = MockClient.return_value
        client.create_page.return_value = {
            "id": "task-2",
            "properties": {
                "Task": {"title": [{"plain_text": "Test", "text": {"content": "Test"}}]},
                "Status": {"select": {"name": "In Progress"}},
                "Priority": {"select": None}, "Project": {"select": None},
                "Due Date": {"date": None}, "Notes": {"rich_text": []},
                "Parent item": {"relation": []},
            },
            "url": "https://notion.so/task-2",
        }
        client.get_page.return_value = client.create_page.return_value

        add_task("Test", status="In Progress")

        props = client.create_page.call_args[0][1]
        assert props["Status"] == {"select": {"name": "In Progress"}}
