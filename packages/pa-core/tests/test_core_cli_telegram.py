"""Tests for Telegram acknowledgment in pa_core.cli (checkin + context commands)."""

import json
from unittest.mock import patch, MagicMock, call

import pytest


FAKE_NOW = {
    "date": "2026-03-19",
    "day": "Thursday",
    "time": "10:00",
    "timezone": "Europe/London",
    "period": "morning",
    "display": "Thursday 19 March 2026, 10:00 GMT",
}

FAKE_CTX = {
    "now": FAKE_NOW,
    "calendar": [],
    "emails": [],
    "telegram_messages": [
        {"update_id": 1, "date": "2026-03-19", "time": "09:00", "text": "reminder", "from_name": "Alice"},
    ],
    "tasks_due_soon": [],
    "tasks_urgent": [],
    "completed_today": [],
    "completed_yesterday": [],
    "stats": {
        "completed_today_count": 0, "completed_yesterday_count": 0,
        "completed_7d_count": 0, "completed_30d_count": 0,
        "avg_daily_7d": 0, "avg_daily_30d": 0, "task_streak": 0,
    },
    "habits": [],
    "weather": {"location": "London", "temperature": 12, "feels_like": 10,
                "description": "Cloudy", "high": 14, "low": 8,
                "rain_probability": 20, "wind_speed": 15},
    "errors": [],
}


# ---------------------------------------------------------------------------
# cmd_context
# ---------------------------------------------------------------------------

class TestCmdContextTelegram:
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    def test_context_acknowledges_messages(self, _ctx, _render, mock_ack, capsys):
        with patch("sys.argv", ["pa-core", "context"]):
            from pa_core.cli import main
            main()
        mock_ack.assert_called_once_with(FAKE_CTX["telegram_messages"])

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context")
    def test_context_no_messages_skips_ack(self, mock_ctx, _render, mock_ack, capsys):
        ctx_no_msgs = {**FAKE_CTX, "telegram_messages": []}
        mock_ctx.return_value = ctx_no_msgs
        with patch("sys.argv", ["pa-core", "context"]):
            from pa_core.cli import main
            main()
        mock_ack.assert_not_called()

    @patch("pa_telegram.client.acknowledge_messages", side_effect=RuntimeError("fail"))
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    def test_context_ack_failure_silent(self, _ctx, _render, _ack, capsys):
        """Ack failure should not crash the context command."""
        with patch("sys.argv", ["pa-core", "context"]):
            from pa_core.cli import main
            main()  # Should not raise

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    def test_context_json_also_acknowledges(self, _ctx, mock_ack, capsys):
        with patch("sys.argv", ["pa-core", "context", "--json"]):
            from pa_core.cli import main
            main()
        mock_ack.assert_called_once()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "telegram_messages" in data


# ---------------------------------------------------------------------------
# cmd_checkin
# ---------------------------------------------------------------------------

class TestCmdCheckinTelegram:
    @patch("pa_google.drive.run_backup", return_value={"filename": "backup.tar.gz"})
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered context")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_acknowledges_after_output(self, _sync, _ctx, _render, mock_ack, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        mock_ack.assert_called_once_with(FAKE_CTX["telegram_messages"])

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered context")
    @patch("pa_core.context.get_today_context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_no_messages_skips_ack(self, _sync, mock_ctx, _render, mock_ack, capsys):
        ctx_no_msgs = {**FAKE_CTX, "telegram_messages": []}
        mock_ctx.return_value = ctx_no_msgs
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        mock_ack.assert_not_called()


# ---------------------------------------------------------------------------
# cmd_checkin — ordering
# ---------------------------------------------------------------------------

class TestCheckinOrdering:
    """Verify the checkin steps run in the correct order."""

    @patch("pa_google.drive.run_backup", return_value={"filename": "backup.tar.gz"})
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_backup_runs_last(self, mock_sync, mock_ctx, _render, mock_ack, mock_backup, capsys):
        """Backup should run after ack (which is after coaching)."""
        call_order = []
        mock_sync.side_effect = lambda: (call_order.append("sync"), [])[1]
        mock_ctx.side_effect = lambda: (call_order.append("context"), FAKE_CTX)[1]
        mock_ack.side_effect = lambda msgs: call_order.append("ack")
        mock_backup.side_effect = lambda: (call_order.append("backup"), {"filename": "b.tar.gz"})[1]

        with patch("sys.argv", ["pa-core", "checkin"]):
            from pa_core.cli import main
            main()

        assert call_order.index("sync") < call_order.index("context")
        assert call_order.index("context") < call_order.index("ack")
        assert call_order.index("ack") < call_order.index("backup")

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_no_backup_flag_skips_backup(self, _sync, _ctx, _render, _ack, capsys):
        """--no-backup should skip the backup step entirely."""
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            with patch("pa_google.drive.run_backup") as mock_backup:
                from pa_core.cli import main
                main()
            mock_backup.assert_not_called()

    @patch("pa_google.drive.run_backup", return_value={"filename": "backup.tar.gz"})
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_backup_success_prints_filename(self, _sync, _ctx, _render, _ack, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin"]):
            from pa_core.cli import main
            main()
        assert "Backup uploaded: backup.tar.gz" in capsys.readouterr().err

    @patch("pa_google.drive.run_backup", side_effect=RuntimeError("drive down"))
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_backup_failure_prints_error(self, _sync, _ctx, _render, _ack, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin"]):
            from pa_core.cli import main
            main()
        assert "Backup failed: drive down" in capsys.readouterr().err

    @patch("pa_telegram.client.acknowledge_messages", side_effect=RuntimeError("ack fail"))
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_ack_failure_silent(self, _sync, _ctx, _render, _ack, capsys):
        """Ack failure in checkin should not crash."""
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()  # Should not raise


# ---------------------------------------------------------------------------
# cmd_checkin — coaching prompt
# ---------------------------------------------------------------------------

class TestCheckinCoaching:
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_morning_coaching_prompt(self, _sync, _ctx, _render, _ack, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "Morning Session" in out
        assert "wellness check-in" in out

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_evening_coaching_prompt(self, _sync, mock_ctx, _render, _ack, capsys):
        evening_ctx = {**FAKE_CTX, "now": {**FAKE_NOW, "period": "evening"}}
        mock_ctx.return_value = evening_ctx
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "Evening Session" in out

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_evening_flag_overrides_period(self, _sync, _ctx, _render, _ack, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup", "--evening"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "Evening Session" in out

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_json_mode_no_coaching(self, _sync, _ctx, _ack, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup", "--json"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "Morning Session" not in out
        assert "Evening Session" not in out
        # Should be valid JSON
        data = json.loads(out)
        assert "telegram_messages" in data


# ---------------------------------------------------------------------------
# cmd_checkin — sync reporting
# ---------------------------------------------------------------------------

class TestCheckinSync:
    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_core.daily_log.log_event")
    @patch("pa_notion.tasks.sync_google_tasks")
    def test_sync_completed_tasks(self, mock_sync, mock_log, _ctx, _render, _ack, capsys):
        mock_sync.return_value = [{"title": "Buy milk", "status": "Done"}]
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        err = capsys.readouterr().err
        assert "synced 1 completed" in err

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_core.daily_log.log_event")
    @patch("pa_notion.tasks.sync_google_tasks")
    def test_sync_imported_tasks(self, mock_sync, mock_log, _ctx, _render, _ack, capsys):
        mock_sync.return_value = [{"title": "New task", "status": "To Do"}]
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        err = capsys.readouterr().err
        assert "imported 1 new" in err

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_core.context.render_context", return_value="rendered")
    @patch("pa_core.context.get_today_context", return_value=FAKE_CTX)
    @patch("pa_notion.tasks.sync_google_tasks", side_effect=RuntimeError("sync fail"))
    def test_sync_failure_continues(self, _sync, _ctx, _render, _ack, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()  # Should not crash
        err = capsys.readouterr().err
        assert "Task sync failed" in err
