"""Tests for task stats computation and ASCII rendering."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pa_notion.stats import get_task_stats, render_bar, render_stats


# ---------------------------------------------------------------------------
# render_bar
# ---------------------------------------------------------------------------


class TestRenderBar:
    def test_basic_bar(self):
        result = render_bar("Project A", 10, 20, width=20)
        assert "Project A" in result
        assert "10" in result
        # Half-width bar
        assert "\u2588" * 10 in result

    def test_zero_value(self):
        result = render_bar("Empty", 0, 20, width=20)
        assert "Empty" in result
        assert "0" in result
        assert "\u2588" not in result

    def test_max_value(self):
        result = render_bar("Full", 20, 20, width=20)
        assert "\u2588" * 20 in result

    def test_zero_max_no_crash(self):
        result = render_bar("None", 0, 0, width=20)
        assert "None" in result
        assert "0" in result


# ---------------------------------------------------------------------------
# get_task_stats — with mocked Notion data
# ---------------------------------------------------------------------------


def _make_task(status="To Do", project="Admin / Finance", last_edited="2026-03-20T10:00:00.000Z"):
    return {
        "id": "fake-id",
        "title": "Test task",
        "status": status,
        "priority": "Medium",
        "project": project,
        "due_date": "",
        "url": "",
        "last_edited_time": last_edited,
    }


class TestGetTaskStats:
    @patch("pa_notion.stats.list_tasks")
    def test_counts_by_status(self, mock_list):
        mock_list.return_value = [
            _make_task(status="To Do"),
            _make_task(status="To Do"),
            _make_task(status="In Progress"),
            _make_task(status="Done", last_edited="2026-03-20T10:00:00.000Z"),
        ]
        stats = get_task_stats(today="2026-03-23")
        assert stats["by_status"]["To Do"] == 2
        assert stats["by_status"]["In Progress"] == 1
        assert stats["by_status"]["Done"] == 1
        assert stats["total"] == 4

    @patch("pa_notion.stats.list_tasks")
    def test_active_by_project(self, mock_list):
        mock_list.return_value = [
            _make_task(status="To Do", project="Garden"),
            _make_task(status="To Do", project="Garden"),
            _make_task(status="In Progress", project="Admin / Finance"),
            _make_task(status="Done", project="Garden"),  # Done — excluded from active
        ]
        stats = get_task_stats(today="2026-03-23")
        assert stats["active_by_project"]["Garden"] == 2
        assert stats["active_by_project"]["Admin / Finance"] == 1
        assert "Garden" not in stats["active_by_project"] or stats["active_by_project"]["Garden"] == 2

    @patch("pa_notion.stats.list_tasks")
    def test_completed_last_7d(self, mock_list):
        mock_list.return_value = [
            _make_task(status="Done", last_edited="2026-03-20T10:00:00.000Z"),
            _make_task(status="Done", last_edited="2026-03-20T15:00:00.000Z"),
            _make_task(status="Done", last_edited="2026-03-18T08:00:00.000Z"),
            _make_task(status="Done", last_edited="2026-03-10T08:00:00.000Z"),  # outside 7 days
        ]
        stats = get_task_stats(today="2026-03-23")
        daily = {d["date"]: d["count"] for d in stats["completed_last_7d"]}
        assert daily["2026-03-20"] == 2
        assert daily["2026-03-18"] == 1
        # Mar 10 is outside 7-day window
        assert "2026-03-10" not in daily

    @patch("pa_notion.stats.list_tasks")
    def test_completed_by_project_7d(self, mock_list):
        mock_list.return_value = [
            _make_task(status="Done", project="Garden", last_edited="2026-03-20T10:00:00.000Z"),
            _make_task(status="Done", project="Garden", last_edited="2026-03-19T10:00:00.000Z"),
            _make_task(status="Done", project="Admin / Finance", last_edited="2026-03-21T10:00:00.000Z"),
        ]
        stats = get_task_stats(today="2026-03-23")
        assert stats["completed_by_project_7d"]["Garden"] == 2
        assert stats["completed_by_project_7d"]["Admin / Finance"] == 1

    @patch("pa_notion.stats.list_tasks")
    def test_active_and_done_counts(self, mock_list):
        mock_list.return_value = [
            _make_task(status="To Do"),
            _make_task(status="In Progress"),
            _make_task(status="Done"),
            _make_task(status="Done"),
        ]
        stats = get_task_stats(today="2026-03-23")
        assert stats["active"] == 2
        assert stats["done"] == 2


# ---------------------------------------------------------------------------
# render_stats — integration test on rendered output
# ---------------------------------------------------------------------------


class TestRenderStats:
    def test_contains_section_headers(self):
        stats = {
            "by_status": {"To Do": 5, "In Progress": 2, "Done": 10},
            "active_by_project": {"Garden": 3, "Admin / Finance": 2},
            "completed_last_7d": [
                {"date": "2026-03-17", "day": "Mon", "count": 3},
                {"date": "2026-03-18", "day": "Tue", "count": 1},
            ],
            "completed_by_project_7d": {"Garden": 2},
            "completed_by_project_30d": {"Garden": 5, "Admin / Finance": 3},
            "total": 17, "active": 7, "done": 10,
        }
        output = render_stats(stats)
        assert "Tasks by Status" in output
        assert "Tasks by Project" in output
        assert "Completed last 7 days" in output
        assert "Completed by project (7 days)" in output
        assert "Completed by project (30 days)" in output

    def test_shows_values(self):
        stats = {
            "by_status": {"To Do": 77, "Done": 84},
            "active_by_project": {"House Renovation": 24},
            "completed_last_7d": [{"date": "2026-03-20", "day": "Thu", "count": 8}],
            "completed_by_project_7d": {"House Renovation": 5},
            "completed_by_project_30d": {"House Renovation": 12},
            "total": 161, "active": 77, "done": 84,
        }
        output = render_stats(stats)
        assert "77" in output
        assert "84" in output
        assert "House Renovation" in output
