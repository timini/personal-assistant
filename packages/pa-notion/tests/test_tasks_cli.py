"""Tests for the task fields and CLI options agents previously scripted by hand."""

import json
from unittest.mock import patch

import pytest

from pa_notion import cli
from pa_notion.tasks import _extract_task, add_task, filter_tasks, update_task


def _page(title="Fix gate", notes="", status="To Do", lane="", project="Home", due=None):
    return {
        "id": "task-1",
        "url": "https://notion.so/task-1",
        "properties": {
            "Task": {"title": [{"plain_text": title}]},
            "Status": {"select": {"name": status}},
            "Priority": {"select": None},
            "Lane": {"select": {"name": lane} if lane else None},
            "Project": {"select": {"name": project}},
            "Due Date": {"date": {"start": due} if due else None},
            "Notes": {"rich_text": [{"plain_text": notes[:3]}, {"plain_text": notes[3:]}] if notes else []},
        },
    }


def _run(argv, capsys):
    with patch.object(cli.sys, "argv", ["pa-notion", *argv]):
        cli.main()
    return capsys.readouterr().out


def test_extract_task_includes_notes_joined_across_segments():
    assert _extract_task(_page(notes="Quote received"))["notes"] == "Quote received"


@patch("pa_notion.tasks.NotionClient")
def test_append_notes_keeps_existing_text(MockClient):
    client = MockClient.return_value
    client.get_page.side_effect = [_page(notes="Old note"), _page(notes="Old note\n\nNew fact")]

    update_task("task-1", append_notes="New fact")

    written = client.update_page.call_args[0][1]["Notes"]["rich_text"]
    assert "".join(seg["text"]["content"] for seg in written) == "Old note\n\nNew fact"


@patch("pa_notion.tasks.NotionClient")
def test_append_notes_to_empty_notes_has_no_leading_gap(MockClient):
    client = MockClient.return_value
    client.get_page.side_effect = [_page(), _page(notes="First")]

    update_task("task-1", append_notes="First")

    written = client.update_page.call_args[0][1]["Notes"]["rich_text"]
    assert written[0]["text"]["content"] == "First"


@patch("pa_notion.tasks.NotionClient")
def test_update_sets_lane_and_clears_due(MockClient):
    client = MockClient.return_value
    client.get_page.return_value = _page(lane="🅿️ Parked")

    update_task("task-1", lane="🅿️ Parked", due_date=None)

    props = client.update_page.call_args[0][1]
    assert props["Lane"] == {"select": {"name": "🅿️ Parked"}}
    assert props["Due Date"] == {"date": None}


@patch("pa_notion.tasks.list_tasks", return_value=[])
@patch("pa_notion.tasks.NotionClient")
def test_add_task_sets_due_and_lane(MockClient, _list):
    client = MockClient.return_value
    client.create_page.return_value = _page(due="2026-11-01")
    client.get_page.return_value = _page(due="2026-11-01")

    add_task("Fix gate", due_date="2026-11-01", lane="🔥 Live")

    props = client.create_page.call_args[0][1]
    assert props["Due Date"] == {"date": {"start": "2026-11-01"}}
    assert props["Lane"] == {"select": {"name": "🔥 Live"}}


TASKS = [
    {"id": "1", "title": "Order ducting", "status": "To Do", "project": "House", "lane": "🔥 Live",
     "due_date": "2026-10-25", "notes": "Supplier quote attached"},
    {"id": "2", "title": "Book dentist", "status": "Done", "project": "Health", "lane": "",
     "due_date": "2026-10-01", "notes": ""},
    {"id": "3", "title": "Renew passport", "status": "In Progress", "project": "Admin", "lane": "",
     "due_date": "", "notes": ""},
]


def test_filter_open_excludes_done_and_discarded():
    assert [t["id"] for t in filter_tasks(TASKS, open_only=True)] == ["1", "3"]


def test_filter_search_matches_title_and_notes_case_insensitively():
    assert [t["id"] for t in filter_tasks(TASKS, search="SUPPLIER")] == ["1"]
    assert [t["id"] for t in filter_tasks(TASKS, search="passport")] == ["3"]


def test_filter_project_lane_and_due_before():
    assert [t["id"] for t in filter_tasks(TASKS, project="house")] == ["1"]
    assert [t["id"] for t in filter_tasks(TASKS, lane="Live")] == ["1"]
    # Tasks without a due date never match a due-before filter.
    assert [t["id"] for t in filter_tasks(TASKS, due_before="2026-10-26")] == ["1", "2"]


def test_cli_list_applies_filters(capsys):
    with patch("pa_notion.cli.list_tasks", return_value=TASKS):
        out = _run(["tasks", "list", "--open", "--search", "ducting", "--json"], capsys)
    assert [t["id"] for t in json.loads(out)] == ["1"]


def test_cli_show_prints_notes_and_body(capsys):
    task = dict(TASKS[0], url="https://notion.so/1", priority="High")
    with patch("pa_notion.cli.get_task", return_value=task), \
         patch("pa_notion.cli.get_task_body", return_value="Checklist:\n- measure"):
        out = _run(["tasks", "show", "1"], capsys)
    assert "Order ducting" in out
    assert "Supplier quote attached" in out
    assert "- measure" in out


def test_cli_update_append_notes_and_due_none(capsys):
    with patch("pa_notion.cli.update_task", return_value={"title": "Order ducting"}) as m:
        _run(["tasks", "update", "1", "--append-notes", "Chased supplier", "--due", "none"], capsys)
    assert m.call_args.kwargs == {"append_notes": "Chased supplier", "due_date": None}


def test_cli_update_rejects_notes_and_append_notes_together(capsys):
    with pytest.raises(SystemExit):
        _run(["tasks", "update", "1", "--notes", "a", "--append-notes", "b"], capsys)
