"""Tests for pa_browser.chrome — the osascript/JXA bridge (run_cli mocked, no real Chrome)."""

import base64
from unittest.mock import Mock, patch

import pytest

from pa_browser import chrome


def _proc(stdout="", returncode=0, stderr=""):
    return Mock(stdout=stdout, returncode=returncode, stderr=stderr)


def _script_of(mock_run):
    """Extract the JXA script (last element of the osascript command) from the run_cli call."""
    command = mock_run.call_args.args[0]
    assert command[0] == "osascript"
    return command[-1]


def test_list_tabs_parses_json():
    out = '[{"window":0,"index":1,"title":"Gmail","url":"https://mail.google.com","loading":false}]'
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout=out)) as m:
        tabs = chrome.list_tabs()
    assert tabs == [{"window": 0, "index": 1, "title": "Gmail", "url": "https://mail.google.com", "loading": False}]
    assert "windows" in _script_of(m)


def test_read_url_builds_script_and_returns_text():
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout="authenticated page text")) as m:
        text = chrome.read_url("https://portal.example.com/account")
    assert text == "authenticated page text"
    script = _script_of(m)
    assert "portal.example.com/account" in script   # URL embedded
    assert "innerText" in script                      # reads body text


def test_exec_js_embeds_payload_as_base64():
    js = "document.querySelectorAll('td').length"
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout="42")) as m:
        result = chrome.exec_js("https://x.test", js)
    assert result == "42"
    script = _script_of(m)
    b64 = base64.b64encode(js.encode()).decode()
    assert b64 in script           # payload passed safely as base64
    assert "atob" in script        # decoded in-page


def test_exec_js_async_uses_title_channel():
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout='{"ok":true}')) as m:
        chrome.exec_js("https://x.test", "fetch('/api')", async_=True)
    assert chrome.PA_MARKER in _script_of(m)   # polls document.title for the marker


def test_eval_tab_targets_existing_tab_without_opening():
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout="ok")) as m:
        chrome.eval_tab(3, "document.title")
    script = _script_of(m)
    assert "3" in script
    assert "c.Tab(" not in script and "Tab({" not in script   # does not create a new tab


def test_err_prefix_raises_chrome_error():
    with patch("pa_browser.chrome.run_cli", return_value=_proc(stdout="ERR:Chrome not running")):
        with pytest.raises(chrome.ChromeError):
            chrome.read_url("https://x.test")


def test_apple_events_js_disabled_gives_clear_message():
    proc = _proc(stdout="", returncode=1, stderr="execution error: Error: Message not understood. (-1708)")
    with patch("pa_browser.chrome.run_cli", return_value=proc):
        with pytest.raises(chrome.ChromeError, match="Allow JavaScript from Apple Events"):
            chrome.read_url("https://x.test")


def test_osascript_failure_raises_chrome_error():
    proc = _proc(stdout="", returncode=1, stderr="Google Chrome got an error: Application isn't running")
    with patch("pa_browser.chrome.run_cli", return_value=proc):
        with pytest.raises(chrome.ChromeError):
            chrome.list_tabs()
