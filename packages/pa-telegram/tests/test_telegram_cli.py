"""Tests for pa_telegram.cli — send, messages, and briefing subcommands."""

import json
import sys
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# cmd_messages
# ---------------------------------------------------------------------------

class TestCmdMessages:
    def _run(self, argv):
        """Run pa-telegram CLI with given argv."""
        with patch("sys.argv", ["pa-telegram"] + argv):
            from pa_telegram.cli import main
            main()

    @patch("pa_telegram.client.get_messages", return_value=[])
    def test_no_messages(self, _gm, capsys):
        self._run(["messages"])
        assert "No new messages." in capsys.readouterr().out

    @patch("pa_telegram.client.get_messages", return_value=[
        {"date": "2026-03-19", "time": "14:48", "from_name": "Tim", "text": "hello", "update_id": 1},
    ])
    def test_messages_text_output(self, _gm, capsys):
        self._run(["messages"])
        out = capsys.readouterr().out
        assert "[2026-03-19 14:48] Tim: hello" in out

    @patch("pa_telegram.client.get_messages", return_value=[
        {"date": "2026-03-19", "time": "14:48", "from_name": "Tim", "text": "hello", "update_id": 1},
    ])
    def test_messages_json_output(self, _gm, capsys):
        self._run(["messages", "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["text"] == "hello"

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_telegram.client.get_messages", return_value=[
        {"date": "2026-03-19", "time": "14:48", "from_name": "Tim", "text": "hello", "update_id": 1},
    ])
    def test_messages_ack(self, _gm, mock_ack, capsys):
        self._run(["messages", "--ack"])
        mock_ack.assert_called_once()
        assert "Acknowledged 1 message(s)." in capsys.readouterr().out

    @patch("pa_telegram.client.acknowledge_messages")
    @patch("pa_telegram.client.get_messages", return_value=[])
    def test_messages_ack_no_messages_skips_ack(self, _gm, mock_ack, capsys):
        self._run(["messages", "--ack"])
        mock_ack.assert_not_called()

    @patch("pa_telegram.client.get_messages", side_effect=RuntimeError("API down"))
    def test_messages_error(self, _gm, capsys):
        with pytest.raises(SystemExit):
            self._run(["messages"])
        assert "API down" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# cmd_send
# ---------------------------------------------------------------------------

class TestCmdSend:
    def _run(self, argv):
        with patch("sys.argv", ["pa-telegram"] + argv):
            from pa_telegram.cli import main
            main()

    @patch("pa_telegram.client.send_message")
    def test_send_success(self, mock_send, capsys):
        self._run(["send", "hello world"])
        mock_send.assert_called_once_with("hello world")
        assert "Message sent" in capsys.readouterr().out

    @patch("pa_telegram.client.send_message", side_effect=RuntimeError("fail"))
    def test_send_error(self, _send, capsys):
        with pytest.raises(SystemExit):
            self._run(["send", "hello"])
        assert "fail" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# cmd_briefing
# ---------------------------------------------------------------------------

class TestCmdBriefing:
    def _run(self, argv):
        with patch("sys.argv", ["pa-telegram"] + argv):
            from pa_telegram.cli import main
            main()

    @patch("pa_telegram.client.send_briefing")
    def test_briefing_morning(self, mock_sb, capsys):
        self._run(["briefing"])
        mock_sb.assert_called_once_with(date=None)
        assert "Briefing sent" in capsys.readouterr().out

    @patch("pa_telegram.client.send_evening_briefing")
    def test_briefing_evening(self, mock_seb, capsys):
        self._run(["briefing", "--evening"])
        mock_seb.assert_called_once_with(date=None)
        assert "Evening briefing sent" in capsys.readouterr().out

    @patch("pa_telegram.client.send_briefing")
    def test_briefing_with_date(self, mock_sb, capsys):
        self._run(["briefing", "--date", "2026-03-19"])
        mock_sb.assert_called_once_with(date="2026-03-19")

    @patch("pa_telegram.client.send_briefing", side_effect=RuntimeError("oops"))
    def test_briefing_error(self, _sb, capsys):
        with pytest.raises(SystemExit):
            self._run(["briefing"])
        assert "oops" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main (no subcommand)
# ---------------------------------------------------------------------------

class TestMain:
    def test_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["pa-telegram"]):
            from pa_telegram.cli import main
            main()
        out = capsys.readouterr().out
        assert "usage" in out.lower() or "send" in out.lower()
