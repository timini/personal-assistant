"""Guards against task noise and Notion's text limits."""

from unittest.mock import patch

import pytest

from pa_notion import tasks
from pa_notion.tasks import DuplicateTaskError, add_task, find_similar_tasks, update_task


def _page(task_id="t1", title="Test"):
    return {
        "id": task_id,
        "properties": {
            "Task": {"title": [{"plain_text": title}]},
            "Status": {"select": {"name": "To Do"}},
        },
        "url": f"https://notion.so/{task_id}",
    }


OPEN = [
    {"id": "a", "title": "Pay plumber invoice", "status": "To Do"},
    {"id": "b", "title": "Book car service", "status": "Waiting"},
    {"id": "c", "title": "Renew passport", "status": "Done"},
]


class TestRichTextChunking:
    def test_long_notes_split_into_2000_char_segments(self):
        chunks = tasks._rich_text("x" * 4500)
        assert [len(c["text"]["content"]) for c in chunks] == [2000, 2000, 500]

    def test_short_notes_single_segment(self):
        assert tasks._rich_text("hello") == [{"text": {"content": "hello"}}]

    @patch("pa_notion.tasks.list_tasks", return_value=[])
    @patch("pa_notion.tasks.NotionClient")
    @patch("pa_notion.tasks._get_db_id", return_value="db")
    def test_add_task_chunks_notes(self, _db, MockClient, _list):
        client = MockClient.return_value
        client.create_page.return_value = client.get_page.return_value = _page()
        add_task("Test", notes="y" * 2500)
        notes = client.create_page.call_args[0][1]["Notes"]["rich_text"]
        assert len(notes) == 2

    @patch("pa_notion.tasks.NotionClient")
    def test_update_task_chunks_notes(self, MockClient):
        client = MockClient.return_value
        client.get_page.return_value = _page()
        update_task("t1", notes="z" * 3000)
        notes = client.update_page.call_args[0][1]["Notes"]["rich_text"]
        assert len(notes) == 2


class TestDuplicateDetection:
    def test_finds_near_match_among_open_tasks(self):
        matches = find_similar_tasks("Pay the plumber invoice", OPEN)
        assert [m["id"] for m in matches] == ["a"]

    def test_ignores_done_tasks(self):
        assert find_similar_tasks("Renew passport", OPEN) == []

    def test_unrelated_title_has_no_match(self):
        assert find_similar_tasks("Water the garden", OPEN) == []

    @patch("pa_notion.tasks.list_tasks", return_value=OPEN)
    @patch("pa_notion.tasks.NotionClient")
    @patch("pa_notion.tasks._get_db_id", return_value="db")
    def test_add_task_refuses_duplicate(self, _db, MockClient, _list):
        with pytest.raises(DuplicateTaskError) as err:
            add_task("Pay plumber invoice")
        assert err.value.matches[0]["id"] == "a"
        MockClient.return_value.create_page.assert_not_called()

    @patch("pa_notion.tasks.list_tasks", return_value=OPEN)
    @patch("pa_notion.tasks.NotionClient")
    @patch("pa_notion.tasks._get_db_id", return_value="db")
    def test_add_task_force_creates_anyway(self, _db, MockClient, _list):
        client = MockClient.return_value
        client.create_page.return_value = client.get_page.return_value = _page()
        add_task("Pay plumber invoice", force=True)
        client.create_page.assert_called_once()


class TestCli:
    @patch("pa_notion.tasks.list_tasks", return_value=OPEN)
    def test_cli_add_duplicate_exits_with_match(self, _list, capsys):
        from pa_notion.cli import main
        with patch("sys.argv", ["pa-notion", "tasks", "add", "Pay plumber invoice"]):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "Pay plumber invoice" in err and "--force" in err


def test_google_tasks_integration_removed():
    for name in ("sync_google_tasks", "promote_task", "import_orphaned_tasks", "GOOGLE_TASK_LISTS"):
        assert not hasattr(tasks, name)
