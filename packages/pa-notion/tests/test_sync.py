"""Tests for Google Tasks ↔ Notion sync logic."""

from unittest.mock import patch, MagicMock

import pytest

from pa_notion.tasks import sync_google_tasks, import_orphaned_tasks


# ---------------------------------------------------------------------------
# Phase 2: sync_google_tasks — skip tasks already Done in Notion
# ---------------------------------------------------------------------------


class TestSyncSkipsAlreadyDone:
    """Completed Google Tasks linked to Notion tasks that are already Done
    should be silently skipped — no update, no delete, not in results."""

    @patch("pa_notion.tasks.run_gws")
    @patch("pa_notion.tasks.get_task")
    @patch("pa_notion.tasks.update_task")
    @patch("pa_notion.tasks.import_orphaned_tasks", return_value=[])
    def test_already_done_not_in_synced_list(self, _import, mock_update, mock_get, mock_gws):
        """A task already Done in Notion should be skipped entirely."""
        mock_gws.return_value = {
            "items": [{
                "id": "gt1",
                "status": "completed",
                "completed": "2026-01-23T11:20:21.329Z",
                "title": "Old task",
                "notes": "https://www.notion.so/aaaabbbbccccddddeeeeffffaaaabbbb",
            }]
        }
        mock_get.return_value = {"id": "aaaa-bbbb", "title": "Old task", "status": "Done",
                                 "priority": "", "project": "", "due_date": "", "url": ""}

        result = sync_google_tasks()

        assert len(result) == 0, "Already-Done tasks should not appear in sync results"
        mock_update.assert_not_called()

    @patch("pa_notion.tasks.run_gws")
    @patch("pa_notion.tasks.get_task")
    @patch("pa_notion.tasks.update_task")
    @patch("pa_notion.tasks.import_orphaned_tasks", return_value=[])
    def test_already_done_not_deleted_from_google(self, _import, mock_update, mock_get, mock_gws):
        """Already-Done tasks should NOT be deleted from Google Tasks."""
        mock_gws.return_value = {
            "items": [{
                "id": "gt1",
                "status": "completed",
                "completed": "2026-01-23T11:20:21.329Z",
                "title": "Old task",
                "notes": "https://www.notion.so/aaaabbbbccccddddeeeeffffaaaabbbb",
            }]
        }
        mock_get.return_value = {"id": "aaaa-bbbb", "title": "Old task", "status": "Done",
                                 "priority": "", "project": "", "due_date": "", "url": ""}

        sync_google_tasks()

        # Should NOT call delete — completed tasks stay in Google Tasks
        delete_calls = [c for c in mock_gws.call_args_list
                        if len(c[0]) >= 3 and c[0][2] == "delete"]
        assert len(delete_calls) == 0

    @patch("pa_notion.tasks.run_gws")
    @patch("pa_notion.tasks.get_task")
    @patch("pa_notion.tasks.update_task")
    @patch("pa_notion.tasks.import_orphaned_tasks", return_value=[])
    def test_not_done_gets_synced_without_delete(self, _import, mock_update, mock_get, mock_gws):
        """A completed Google Task linked to a non-Done Notion task SHOULD be synced
        but NOT deleted from Google Tasks."""
        mock_gws.return_value = {
            "items": [{
                "id": "gt2",
                "status": "completed",
                "completed": "2026-03-20T10:00:00.000Z",
                "title": "Recent task",
                "notes": "https://www.notion.so/11112222333344445555666677778888",
            }]
        }
        mock_get.return_value = {"id": "1111-2222", "title": "Recent task", "status": "In Progress",
                                 "priority": "", "project": "", "due_date": "", "url": ""}
        mock_update.return_value = {"id": "1111-2222", "title": "Recent task", "status": "Done",
                                    "priority": "", "project": "", "due_date": "", "url": ""}

        result = sync_google_tasks()

        assert len(result) == 1
        assert result[0]["title"] == "Recent task"
        mock_update.assert_called_once()
        # No deletes
        delete_calls = [c for c in mock_gws.call_args_list
                        if len(c[0]) >= 3 and c[0][2] == "delete"]
        assert len(delete_calls) == 0


# ---------------------------------------------------------------------------
# Phase 1: import_orphaned_tasks — skip old completed orphans
# ---------------------------------------------------------------------------


class TestImportOrphansSkipsOld:
    """Completed orphan tasks older than 7 days should be skipped entirely."""

    @patch("pa_notion.tasks.run_gws")
    @patch("pa_notion.tasks.add_task")
    def test_old_completed_orphan_skipped(self, mock_add, mock_gws):
        """A completed orphan from January should be skipped, not imported."""
        mock_gws.return_value = {
            "items": [{
                "id": "gt_old",
                "status": "completed",
                "completed": "2026-01-23T11:20:21.329Z",
                "title": "Action items from my email",
                "notes": "From:  no-reply@monzo.com some stuff",
            }]
        }

        result = import_orphaned_tasks()

        assert len(result) == 0, "Old orphans should not be imported"
        mock_add.assert_not_called()
        # No deletes either
        delete_calls = [c for c in mock_gws.call_args_list
                        if len(c[0]) >= 3 and c[0][2] == "delete"]
        assert len(delete_calls) == 0

    @patch("pa_notion.tasks.run_gws")
    @patch("pa_notion.tasks.add_task")
    @patch("pa_notion.tasks.update_task")
    def test_recent_completed_orphan_imported_with_link(self, mock_update, mock_add, mock_gws):
        """A completed orphan from today should be imported and get a Notion link
        added to the Google Task (not deleted)."""
        mock_add.return_value = {"id": "new-id", "title": "Fresh task", "status": "",
                                 "priority": "", "project": "", "due_date": "", "url": ""}
        mock_update.return_value = {"id": "new-id", "title": "Fresh task", "status": "Done",
                                    "priority": "", "project": "", "due_date": "", "url": ""}
        mock_gws.return_value = {
            "items": [{
                "id": "gt_new",
                "status": "completed",
                "completed": "2026-03-20T10:00:00.000Z",
                "title": "Fresh task",
                "notes": "",
            }]
        }

        result = import_orphaned_tasks()

        assert len(result) == 1
        mock_add.assert_called_once()
        # Should patch (add Notion link), not delete
        patch_calls = [c for c in mock_gws.call_args_list
                       if len(c[0]) >= 3 and c[0][2] == "patch"]
        assert len(patch_calls) == 1
        delete_calls = [c for c in mock_gws.call_args_list
                        if len(c[0]) >= 3 and c[0][2] == "delete"]
        assert len(delete_calls) == 0
