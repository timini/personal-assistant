"""Tests for pa_core.cli — setup, briefing, log, and main dispatch."""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Keep backup bookkeeping out of the real activity/.state.json."""
    import pa_core.state as state
    monkeypatch.setattr(state, "_state_file", lambda: tmp_path / ".state.json")


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

# ---------------------------------------------------------------------------
# cmd_checkin
# ---------------------------------------------------------------------------

_CTX = {"now": {"period": "morning", "date": "2026-01-05"}, "calendar": [], "due_soon": [], "urgent": []}


class TestCmdCheckin:
    @patch("pa_core.memory.render_brief", return_value="## Memory brief")
    @patch("pa_core.context.get_today_context", return_value=_CTX)
    @patch("pa_core.context.render_context", return_value="# Context")
    def test_checkin_prints_morning_prompt_and_memory(self, _render, _ctx, _brief, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "# Context" in out
        assert "## Memory brief" in out
        assert "Reply with:" in out

    @patch("pa_core.memory.render_brief", return_value="")
    @patch("pa_core.context.get_today_context",
           return_value={**_CTX, "now": {"period": "evening", "date": "2026-01-05"}})
    @patch("pa_core.context.render_context", return_value="# Context")
    def test_checkin_evening_has_no_morning_prompt(self, _render, _ctx, _brief, capsys):
        with patch("sys.argv", ["pa-core", "checkin", "--no-backup"]):
            from pa_core.cli import main
            main()
        out = capsys.readouterr().out
        assert "Reply with:" not in out
        assert "Evening" in out

    def test_checkin_has_no_telegram_flag(self):
        with patch("sys.argv", ["pa-core", "checkin", "--telegram"]):
            from pa_core.cli import main
            with pytest.raises(SystemExit):
                main()

    def test_schedule_checkins_command_removed(self):
        with patch("sys.argv", ["pa-core", "schedule-checkins"]):
            from pa_core.cli import main
            with pytest.raises(SystemExit):
                main()


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
            category="email", action="archived", summary="Cleaned inbox", project=None, details=None, links=None,
        )
        assert "Logged:" in capsys.readouterr().out

    @patch("pa_core.daily_log.log_event")
    def test_log_event_with_project(self, mock_log, capsys):
        mock_log.return_value = {"category": "task", "action": "created", "summary": "New task"}
        with patch("sys.argv", ["pa-core", "log", "task", "created", "New task", "--project", "Day Job"]):
            from pa_core.cli import main
            main()
        mock_log.assert_called_once_with(
            category="task", action="created", summary="New task", project="Day Job", details=None, links=None,
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


# ---------------------------------------------------------------------------
# now and log options
# ---------------------------------------------------------------------------

class TestCmdNow:
    @patch("pa_core.config.get_now", return_value={"date": "2026-10-20", "display": "Tue 20 Oct 09:00"})
    def test_now_prints_json(self, _now, capsys):
        import json
        with patch("sys.argv", ["pa-core", "now"]):
            from pa_core.cli import main
            main()
        assert json.loads(capsys.readouterr().out)["date"] == "2026-10-20"


class TestCmdLogOptions:
    @patch("pa_core.daily_log.log_event")
    def test_log_passes_details_and_links(self, mock_log, capsys):
        mock_log.return_value = {"category": "task", "action": "created", "summary": "s"}
        argv = ["pa-core", "log", "task", "created", "s", "--details", '{"id": "t1"}',
                "--link", "task=https://notion.so/t1", "--link", "email=https://mail/x"]
        with patch("sys.argv", argv):
            from pa_core.cli import main
            main()
        kwargs = mock_log.call_args.kwargs
        assert kwargs["details"] == {"id": "t1"}
        assert kwargs["links"] == {"task": "https://notion.so/t1", "email": "https://mail/x"}

    def test_log_rejects_unknown_category_before_writing(self, capsys):
        with patch("sys.argv", ["pa-core", "log", "nonsense", "x", "y"]), \
             patch("pa_core.daily_log.log_event") as mock_log:
            from pa_core.cli import main
            with pytest.raises(SystemExit):
                main()
        mock_log.assert_not_called()
        assert "habit" in capsys.readouterr().err


class TestBackupOncePerDay:
    @pytest.fixture(autouse=True)
    def today(self, monkeypatch):
        monkeypatch.setattr("pa_core.cli._today", lambda: "2026-10-20", raising=False)

    def test_second_backup_same_day_is_skipped(self, capsys):
        from pa_core.cli import _backup
        with patch("pa_google.drive.run_backup", return_value={"filename": "b.tar.gz"}) as run:
            _backup()
            _backup()
        assert run.call_count == 1
        assert "already done today" in capsys.readouterr().out

    def test_failed_backup_is_retried(self, capsys):
        from pa_core.cli import _backup
        with patch("pa_google.drive.run_backup", side_effect=[RuntimeError("x"), {"filename": "b"}]) as run:
            _backup()
            _backup()
        assert run.call_count == 2
