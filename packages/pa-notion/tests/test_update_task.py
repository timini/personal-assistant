"""Tests for update_task — ensures the title is written to the right property."""

from unittest.mock import patch

from pa_notion.tasks import update_task


def _page(title: str) -> dict:
    return {
        "id": "task-1",
        "properties": {
            "Task": {"title": [{"plain_text": title, "text": {"content": title}}]},
            "Status": {"select": None}, "Priority": {"select": None},
            "Project": {"select": None}, "Due Date": {"date": None},
            "Notes": {"rich_text": []}, "Parent item": {"relation": []},
        },
        "url": "https://notion.so/task-1",
    }


class TestUpdateTaskTitle:
    """The Tasks DB titles its title column "Task", so renames must target it."""

    @patch("pa_notion.tasks.NotionClient")
    def test_title_is_written_to_the_task_property(self, MockClient):
        client = MockClient.return_value
        client.get_page.return_value = _page("New name")

        update_task("task-1", title="New name")

        props = client.update_page.call_args[0][1]
        assert "Task" in props, f"title must be written to the 'Task' property, got {list(props)}"
        assert props["Task"] == {"title": [{"text": {"content": "New name"}}]}
        assert "Name" not in props, "'Name' is not a property of the Tasks DB; Notion rejects it"
