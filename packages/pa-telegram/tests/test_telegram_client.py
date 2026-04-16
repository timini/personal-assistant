"""Tests for pa_telegram.client — send, receive, and acknowledge messages."""

import json
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(update_id, chat_id, text, ts=1711000000, first="Alice", last="Smith"):
    """Build a Telegram Update dict."""
    return {
        "update_id": update_id,
        "message": {
            "date": ts,
            "chat": {"id": chat_id},
            "from": {"first_name": first, "last_name": last},
            "text": text,
        },
    }


def _ok_response(result=None):
    """Build a Telegram-style ok response."""
    return {"ok": True, "result": result or []}


# ---------------------------------------------------------------------------
# _format_for_telegram
# ---------------------------------------------------------------------------

class TestFormatForTelegram:
    def test_h1_converted_to_bold(self):
        from pa_telegram.client import _format_for_telegram
        assert _format_for_telegram("# Hello") == "*Hello*"

    def test_h2_converted_to_bold_with_spacing(self):
        from pa_telegram.client import _format_for_telegram
        assert _format_for_telegram("## Section") == "\n*Section*"

    def test_h3_converted_to_bold(self):
        from pa_telegram.client import _format_for_telegram
        assert _format_for_telegram("### Sub") == "*Sub*"

    def test_plain_text_unchanged(self):
        from pa_telegram.client import _format_for_telegram
        assert _format_for_telegram("hello world") == "hello world"

    def test_multiline(self):
        from pa_telegram.client import _format_for_telegram
        result = _format_for_telegram("# Title\nsome text\n## Section")
        assert "*Title*" in result
        assert "some text" in result
        assert "\n*Section*" in result


# ---------------------------------------------------------------------------
# _split_message
# ---------------------------------------------------------------------------

class TestSplitMessage:
    def test_short_message_single_chunk(self):
        from pa_telegram.client import _split_message
        assert _split_message("short") == ["short"]

    def test_exactly_at_limit(self):
        from pa_telegram.client import _split_message, MAX_MESSAGE_LENGTH
        msg = "a" * MAX_MESSAGE_LENGTH
        assert _split_message(msg) == [msg]

    def test_splits_on_paragraph_boundary(self):
        from pa_telegram.client import _split_message, MAX_MESSAGE_LENGTH
        para1 = "a" * (MAX_MESSAGE_LENGTH - 100)
        para2 = "b" * 200
        msg = f"{para1}\n\n{para2}"
        chunks = _split_message(msg)
        assert len(chunks) == 2
        assert chunks[0] == para1
        assert chunks[1] == para2

    def test_splits_long_paragraph_on_newlines(self):
        from pa_telegram.client import _split_message, MAX_MESSAGE_LENGTH
        # Single paragraph (no double newlines) that exceeds the limit
        lines = ["x" * 100 for _ in range(50)]
        long_para = "\n".join(lines)
        assert len(long_para) > MAX_MESSAGE_LENGTH
        chunks = _split_message(long_para)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= MAX_MESSAGE_LENGTH


# ---------------------------------------------------------------------------
# Offset read/write
# ---------------------------------------------------------------------------

class TestOffset:
    def test_read_offset_no_file(self, tmp_path):
        from pa_telegram import client
        with patch.object(client, "_OFFSET_FILE", tmp_path / ".telegram_offset"):
            assert client._read_offset() is None

    def test_read_offset_empty_file(self, tmp_path):
        from pa_telegram import client
        f = tmp_path / ".telegram_offset"
        f.write_text("")
        with patch.object(client, "_OFFSET_FILE", f):
            assert client._read_offset() is None

    def test_write_and_read_offset(self, tmp_path):
        from pa_telegram import client
        f = tmp_path / ".telegram_offset"
        with patch.object(client, "_OFFSET_FILE", f):
            client._write_offset(42)
            assert client._read_offset() == 42

    def test_write_overwrites(self, tmp_path):
        from pa_telegram import client
        f = tmp_path / ".telegram_offset"
        with patch.object(client, "_OFFSET_FILE", f):
            client._write_offset(10)
            client._write_offset(20)
            assert client._read_offset() == 20


# ---------------------------------------------------------------------------
# get_messages
# ---------------------------------------------------------------------------

class TestGetMessages:
    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_returns_matching_messages(self, _off, _tok, _cid):
        updates = [
            _make_update(1, 111, "hello"),
            _make_update(2, 111, "world"),
        ]
        mock_resp = httpx.Response(200, json=_ok_response(updates))

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            from pa_telegram.client import get_messages
            msgs = get_messages()

        assert len(msgs) == 2
        assert msgs[0]["text"] == "hello"
        assert msgs[0]["update_id"] == 1
        assert msgs[0]["from_name"] == "Alice Smith"
        assert msgs[1]["text"] == "world"
        # Verify offset not passed when None
        call_kwargs = mock_get.call_args
        assert "offset" not in call_kwargs.kwargs.get("params", {})

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=5)
    def test_passes_offset_when_set(self, _off, _tok, _cid):
        mock_resp = httpx.Response(200, json=_ok_response([]))
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            from pa_telegram.client import get_messages
            get_messages()

        params = mock_get.call_args.kwargs["params"]
        assert params["offset"] == 5

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_filters_other_chat_ids(self, _off, _tok, _cid):
        updates = [
            _make_update(1, 111, "mine"),
            _make_update(2, 999, "not mine"),
        ]
        mock_resp = httpx.Response(200, json=_ok_response(updates))
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            msgs = get_messages()

        assert len(msgs) == 1
        assert msgs[0]["text"] == "mine"

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_skips_updates_without_message(self, _off, _tok, _cid):
        updates = [
            {"update_id": 1},  # no message key
            _make_update(2, 111, "real"),
        ]
        mock_resp = httpx.Response(200, json=_ok_response(updates))
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            msgs = get_messages()

        assert len(msgs) == 1
        assert msgs[0]["text"] == "real"

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_skips_messages_without_text(self, _off, _tok, _cid):
        updates = [{
            "update_id": 1,
            "message": {
                "date": 1711000000,
                "chat": {"id": 111},
                "from": {"first_name": "Alice"},
                "photo": [{"file_id": "abc"}],
                # no "text" key
            },
        }]
        mock_resp = httpx.Response(200, json=_ok_response(updates))
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            msgs = get_messages()

        assert len(msgs) == 0

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_api_error_raises(self, _off, _tok, _cid):
        mock_resp = httpx.Response(200, json={"ok": False, "description": "Unauthorized"})
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            with pytest.raises(RuntimeError, match="Unauthorized"):
                get_messages()

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_from_name_without_last_name(self, _off, _tok, _cid):
        updates = [_make_update(1, 111, "hi", first="Alice", last=None)]
        # Remove last_name from the update
        updates[0]["message"]["from"] = {"first_name": "Alice"}
        mock_resp = httpx.Response(200, json=_ok_response(updates))
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            msgs = get_messages()

        assert msgs[0]["from_name"] == "Alice"

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    @patch("pa_telegram.client._read_offset", return_value=None)
    def test_date_and_time_formatted(self, _off, _tok, _cid):
        # 2024-03-21 12:26:40 UTC
        ts = 1711023000
        updates = [_make_update(1, 111, "test", ts=ts)]
        mock_resp = httpx.Response(200, json=_ok_response(updates))
        with patch("httpx.get", return_value=mock_resp):
            from pa_telegram.client import get_messages
            msgs = get_messages()

        # Should have valid date and time format
        assert len(msgs[0]["date"]) == 10  # YYYY-MM-DD
        assert len(msgs[0]["time"]) == 5   # HH:MM


# ---------------------------------------------------------------------------
# acknowledge_messages
# ---------------------------------------------------------------------------

class TestAcknowledgeMessages:
    def test_acknowledge_writes_max_plus_one(self, tmp_path):
        from pa_telegram import client
        f = tmp_path / ".telegram_offset"
        with patch.object(client, "_OFFSET_FILE", f):
            messages = [
                {"update_id": 5, "text": "a"},
                {"update_id": 10, "text": "b"},
                {"update_id": 7, "text": "c"},
            ]
            client.acknowledge_messages(messages)
            assert client._read_offset() == 11

    def test_acknowledge_empty_list_does_nothing(self, tmp_path):
        from pa_telegram import client
        f = tmp_path / ".telegram_offset"
        with patch.object(client, "_OFFSET_FILE", f):
            client.acknowledge_messages([])
            assert not f.exists()


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    def test_send_single_chunk(self, _tok, _cid):
        mock_resp = httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            from pa_telegram.client import send_message
            results = send_message("hello")

        assert len(results) == 1
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["text"] == "hello"
        assert call_json["chat_id"] == "111"
        assert call_json["parse_mode"] == "Markdown"

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    def test_send_api_error_raises(self, _tok, _cid):
        mock_resp = httpx.Response(200, json={"ok": False, "description": "Bad Request"})
        with patch("httpx.post", return_value=mock_resp):
            from pa_telegram.client import send_message
            with pytest.raises(RuntimeError, match="Bad Request"):
                send_message("hello")

    @patch("pa_telegram.client._get_chat_id", return_value="111")
    @patch("pa_telegram.client._get_bot_token", return_value="tok123")
    def test_send_api_error_unknown(self, _tok, _cid):
        mock_resp = httpx.Response(200, json={"ok": False})
        with patch("httpx.post", return_value=mock_resp):
            from pa_telegram.client import send_message
            with pytest.raises(RuntimeError, match="Unknown error"):
                send_message("hello")


# ---------------------------------------------------------------------------
# send_briefing / send_evening_briefing
# ---------------------------------------------------------------------------

class TestSendBriefing:
    @patch("pa_telegram.client.send_message", return_value=[{"ok": True}])
    @patch("pa_telegram.client._format_for_telegram", side_effect=lambda x: x)
    def test_send_briefing(self, _fmt, mock_send):
        with patch("pa_core.briefing.generate_briefing", return_value="# Morning"):
            from pa_telegram.client import send_briefing
            result = send_briefing(date="2026-03-19")

        mock_send.assert_called_once_with("# Morning")
        assert result == [{"ok": True}]

    @patch("pa_telegram.client.send_message", return_value=[{"ok": True}])
    @patch("pa_telegram.client._format_for_telegram", side_effect=lambda x: x)
    def test_send_evening_briefing(self, _fmt, mock_send):
        with patch("pa_core.briefing.generate_evening_briefing", return_value="# Evening"):
            from pa_telegram.client import send_evening_briefing
            result = send_evening_briefing(date="2026-03-19")

        mock_send.assert_called_once_with("# Evening")
        assert result == [{"ok": True}]


# ---------------------------------------------------------------------------
# _get_chat_id
# ---------------------------------------------------------------------------

class TestGetBotToken:
    def test_returns_token(self):
        with patch("pa_telegram.client.get_secret", return_value="my_token"):
            from pa_telegram.client import _get_bot_token
            assert _get_bot_token() == "my_token"


class TestGetChatId:
    def test_missing_chat_id_raises(self):
        with patch("pa_telegram.client.get_user_config", return_value={}):
            from pa_telegram.client import _get_chat_id
            with pytest.raises(KeyError, match="telegram.chat_id"):
                _get_chat_id()

    def test_returns_string(self):
        with patch("pa_telegram.client.get_user_config", return_value={"telegram": {"chat_id": 12345}}):
            from pa_telegram.client import _get_chat_id
            result = _get_chat_id()
            assert result == "12345"
            assert isinstance(result, str)
