"""Tests for pa_core.cli — setup, briefing, log, and main dispatch."""

from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# cmd_setup
# ---------------------------------------------------------------------------

class TestCmdSetup:
    @patch("pa_core.setup.setup")
    def test_setup_calls_setup(self, mock_setup):
        with patch("sys.argv", ["pa-core", "setup"]):
            from pa_core.cli import main
            main()
        mock_setup.assert_called_once()


# ---------------------------------------------------------------------------
# cmd_briefing
# ---------------------------------------------------------------------------

class TestCmdBriefing:
    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_core.briefing.generate_briefing", return_value="# Morning")
    def test_briefing_print(self, mock_gen, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing"]):
            from pa_core.cli import main
            main()
        assert "# Morning" in capsys.readouterr().out

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_core.briefing.save_briefing", return_value="/path/to/briefing.md")
    def test_briefing_save(self, mock_save, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--save"]):
            from pa_core.cli import main
            main()
        mock_save.assert_called_once()
        assert "Saved to" in capsys.readouterr().out

    @patch("pa_core.briefing.generate_briefing", return_value="# Morning")
    def test_briefing_no_backup(self, mock_gen, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--no-backup"]):
            from pa_core.cli import main
            main()
        # Should not crash without backup

    @patch("pa_google.drive.run_backup", side_effect=RuntimeError("backup fail"))
    @patch("pa_core.briefing.generate_briefing", return_value="# Morning")
    def test_briefing_backup_failure(self, _gen, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing"]):
            from pa_core.cli import main
            main()
        assert "Backup failed" in capsys.readouterr().err

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_briefing")
    @patch("pa_core.briefing.generate_briefing", return_value="# Morning")
    def test_briefing_telegram(self, _gen, mock_send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--telegram"]):
            from pa_core.cli import main
            main()
        mock_send.assert_called_once()
        assert "Briefing sent" in capsys.readouterr().out

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_briefing", side_effect=RuntimeError("tg fail"))
    @patch("pa_core.briefing.generate_briefing", return_value="# Morning")
    def test_briefing_telegram_failure(self, _gen, _send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--telegram"]):
            from pa_core.cli import main
            main()
        assert "Telegram send failed" in capsys.readouterr().err

    # Evening briefing
    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_core.briefing.generate_evening_briefing", return_value="# Evening")
    def test_evening_briefing_print(self, mock_gen, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--evening"]):
            from pa_core.cli import main
            main()
        assert "# Evening" in capsys.readouterr().out

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_core.briefing.save_evening_briefing", return_value="/path/to/evening.md")
    def test_evening_briefing_save(self, mock_save, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--evening", "--save"]):
            from pa_core.cli import main
            main()
        mock_save.assert_called_once()

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_evening_briefing")
    @patch("pa_core.briefing.generate_evening_briefing", return_value="# Evening")
    def test_evening_briefing_telegram(self, _gen, mock_send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--evening", "--telegram"]):
            from pa_core.cli import main
            main()
        mock_send.assert_called_once()

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_evening_briefing", side_effect=RuntimeError("tg fail"))
    @patch("pa_core.briefing.generate_evening_briefing", return_value="# Evening")
    def test_evening_briefing_telegram_failure(self, _gen, _send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "briefing", "--evening", "--telegram"]):
            from pa_core.cli import main
            main()
        assert "Telegram send failed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# cmd_checkin — Telegram flag
# ---------------------------------------------------------------------------

class TestCmdCheckinTelegram:
    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_briefing")
    @patch("pa_core.context.get_today_context", return_value={"now": {"period": "morning"}})
    @patch("pa_core.context.render_context", return_value="# Context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_telegram(self, _sync, _render, _ctx, mock_send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--telegram"]):
            from pa_core.cli import main
            main()
        mock_send.assert_called_once()
        assert "Briefing sent" in capsys.readouterr().out

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_evening_briefing")
    @patch("pa_core.context.get_today_context", return_value={"now": {"period": "evening"}})
    @patch("pa_core.context.render_context", return_value="# Context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_telegram_evening(self, _sync, _render, _ctx, mock_send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--evening", "--telegram"]):
            from pa_core.cli import main
            main()
        mock_send.assert_called_once()
        assert "Evening briefing sent" in capsys.readouterr().out

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_telegram.client.send_briefing", side_effect=RuntimeError("tg fail"))
    @patch("pa_core.context.get_today_context", return_value={"now": {"period": "morning"}})
    @patch("pa_core.context.render_context", return_value="# Context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_telegram_failure(self, _sync, _render, _ctx, _send, _backup, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--telegram"]):
            from pa_core.cli import main
            main()
        assert "Telegram send failed" in capsys.readouterr().err

    @patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"})
    @patch("pa_core.context.get_today_context", return_value={"now": {"period": "morning"}})
    @patch("pa_core.context.render_context", return_value="# Context")
    @patch("pa_notion.tasks.sync_google_tasks", return_value=[])
    def test_checkin_no_telegram_by_default(self, _sync, _render, _ctx, _backup, capsys):
        with patch("pa_telegram.client.send_briefing") as mock_send:
            with patch("sys.argv", ["pa-core", "checkin"]):
                from pa_core.cli import main
                main()
            mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# cmd_log
# ---------------------------------------------------------------------------

class TestCmdLog:
    @patch("pa_core.daily_log.log_event")
    def test_log_event(self, mock_log, capsys):
        mock_log.return_value = {"category": "email", "action": "archived", "summary": "Cleaned inbox"}
        with patch("sys.argv", ["pa-core", "log", "email", "archived", "Cleaned inbox"]):
            from pa_core.cli import main
            main()
        mock_log.assert_called_once_with(
            category="email", action="archived", summary="Cleaned inbox", project=None,
        )
        assert "Logged:" in capsys.readouterr().out

    @patch("pa_core.daily_log.log_event")
    def test_log_event_with_project(self, mock_log, capsys):
        mock_log.return_value = {"category": "task", "action": "created", "summary": "New task"}
        with patch("sys.argv", ["pa-core", "log", "task", "created", "New task", "--project", "Day Job"]):
            from pa_core.cli import main
            main()
        mock_log.assert_called_once_with(
            category="task", action="created", summary="New task", project="Day Job",
        )


# ---------------------------------------------------------------------------
# main — no command
# ---------------------------------------------------------------------------

class TestMainNoCommand:
    def test_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["pa-core"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "usage" in out.lower() or "setup" in out.lower()
