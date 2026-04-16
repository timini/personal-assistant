"""Tests for pa_whatsapp.client — wacli wrapper."""

import json
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from pa_whatsapp.client import get_messages, acknowledge_messages, list_chats, _read_offset, _write_offset


@pytest.fixture
def offset_file(tmp_path, monkeypatch):
    """Use a temp offset file."""
    f = tmp_path / ".whatsapp_offset"
    monkeypatch.setattr("pa_whatsapp.client._OFFSET_FILE", f)
    return f


class TestGetMessages:
    @patch("pa_whatsapp.client.run_cli")
    def test_returns_parsed_messages(self, mock_run, offset_file):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {
                    "body": "Hello there",
                    "timestamp": "2026-04-15T10:30:00Z",
                    "pushName": "Laura",
                    "chatName": "Family",
                    "id": "msg123",
                }
            ]),
            stderr="",
        )
        messages = get_messages()
        assert len(messages) == 1
        assert messages[0]["text"] == "Hello there"
        assert messages[0]["from_name"] == "Laura"
        assert messages[0]["chat_name"] == "Family"
        assert messages[0]["message_id"] == "msg123"

    @patch("pa_whatsapp.client.run_cli")
    def test_skips_empty_messages(self, mock_run, offset_file):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"body": "", "timestamp": "2026-04-15T10:30:00Z"}]),
            stderr="",
        )
        messages = get_messages()
        assert len(messages) == 0

    @patch("pa_whatsapp.client.run_cli")
    def test_uses_offset_when_available(self, mock_run, offset_file):
        offset_file.write_text("2026-04-15T09:00:00Z")
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        get_messages()
        cmd = mock_run.call_args[0][0]
        assert "--after" in cmd
        assert "2026-04-15T09:00:00Z" in cmd

    @patch("pa_whatsapp.client.run_cli")
    def test_handles_wacli_error(self, mock_run, offset_file):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not authenticated")
        with pytest.raises(RuntimeError, match="wacli error"):
            get_messages()


class TestAcknowledgeMessages:
    def test_writes_latest_timestamp(self, offset_file):
        messages = [
            {"timestamp": "2026-04-15T09:00:00Z"},
            {"timestamp": "2026-04-15T10:30:00Z"},
            {"timestamp": "2026-04-15T10:00:00Z"},
        ]
        acknowledge_messages(messages)
        assert offset_file.read_text() == "2026-04-15T10:30:00Z"

    def test_noop_for_empty_list(self, offset_file):
        acknowledge_messages([])
        assert not offset_file.exists()


class TestListChats:
    @patch("pa_whatsapp.client.run_cli")
    def test_returns_chats(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"name": "Family", "jid": "123@g.us"}]),
            stderr="",
        )
        chats = list_chats()
        assert len(chats) == 1
        assert chats[0]["name"] == "Family"


class TestOffsetFile:
    def test_read_returns_none_when_missing(self, offset_file):
        assert _read_offset() is None

    def test_read_returns_value(self, offset_file):
        offset_file.write_text("2026-04-15T10:00:00Z")
        assert _read_offset() == "2026-04-15T10:00:00Z"

    def test_write_creates_file(self, offset_file):
        _write_offset("2026-04-15T10:00:00Z")
        assert offset_file.read_text() == "2026-04-15T10:00:00Z"
