"""Tests for pa_browser.cli — arg parsing dispatches to chrome with expected kwargs."""

from unittest.mock import MagicMock, patch

import pytest

from pa_browser import cli


def _run(argv):
    with patch.object(cli.sys, "argv", ["pa-browser", *argv]):
        cli.main()


def test_tabs_json(capsys):
    with patch("pa_browser.cli.chrome.list_tabs", return_value=[{"window": 0, "index": 1, "title": "T", "url": "https://x", "loading": False}]):
        _run(["tabs", "--json"])
    assert '"url": "https://x"' in capsys.readouterr().out


def test_read_calls_driver(capsys):
    with patch("pa_browser.cli.driver.read_url", return_value="page text") as m:
        _run(["read", "https://portal.test"])
    assert m.call_args.args[0] == "https://portal.test"
    assert "page text" in capsys.readouterr().out


def test_read_headless_and_bundled_flags(capsys):
    with patch("pa_browser.cli.driver.read_url", return_value="") as m:
        _run(["read", "https://portal.test", "--headless", "--bundled"])
    assert m.call_args.kwargs["headless"] is True
    assert m.call_args.kwargs["channel"] is None


def test_login_dispatches(capsys):
    with patch("pa_browser.cli.driver.login") as m:
        _run(["login", "https://portal.test"])
    assert m.call_args.args[0] == "https://portal.test"


def test_snapshot_prints_json(capsys):
    with patch("pa_browser.cli.driver.snapshot_url", return_value={"url": "u", "elements": []}):
        _run(["snapshot", "https://x.test"])
    assert '"url": "u"' in capsys.readouterr().out


def test_exec_passes_js_and_async():
    with patch("pa_browser.cli.chrome.exec_js", return_value="ok") as m:
        _run(["exec", "https://x.test", "--js", "1+1", "--async"])
    assert m.call_args.args == ("https://x.test", "1+1")
    assert m.call_args.kwargs["async_"] is True


def test_eval_targets_tab():
    with patch("pa_browser.cli.chrome.eval_tab", return_value="ok") as m:
        _run(["eval", "2", "--js", "document.title"])
    assert m.call_args.args == (2, "document.title")


def test_browser_error_exits_1():
    with patch("pa_browser.cli.driver.read_url", side_effect=cli.driver.BrowserError("nope")):
        with pytest.raises(SystemExit) as exc:
            _run(["read", "https://x.test"])
    assert exc.value.code == 1


def test_legacy_chrome_error_exits_1():
    with patch("pa_browser.cli.chrome.exec_js", side_effect=cli.chrome.ChromeError("nope")):
        with pytest.raises(SystemExit) as exc:
            _run(["exec", "https://x.test", "--js", "1"])
    assert exc.value.code == 1


# --- always-on lifecycle + seed + driving verbs ---


def test_start_dispatches():
    with patch("pa_browser.cli.driver.start_chrome", return_value=9222) as m:
        _run(["start"])
    assert m.called


def test_stop_dispatches():
    with patch("pa_browser.cli.driver.stop_chrome", return_value=True) as m:
        _run(["stop"])
    assert m.called


def test_seed_dispatches():
    with patch("pa_browser.cli.seed.seed_profile", return_value=["Cookies"]) as m:
        _run(["seed"])
    assert m.called


def test_goto_errors_when_not_running():
    with patch("pa_browser.cli.driver.chrome_running", return_value=False):
        with pytest.raises(SystemExit) as exc:
            _run(["goto", "https://x.test"])
    assert exc.value.code == 1


def _attach_cm(fake_ctx):
    cm = MagicMock()
    cm.__enter__ = lambda s: fake_ctx
    cm.__exit__ = lambda s, *a: False
    return cm


def test_fill_dispatches_to_running_page():
    fake_ctx = MagicMock()
    fake_ctx.pages = [MagicMock()]
    with patch("pa_browser.cli.driver.chrome_running", return_value=True), \
         patch("pa_browser.cli.driver.attach", return_value=_attach_cm(fake_ctx)), \
         patch("pa_browser.cli.driver.fill") as mf:
        _run(["fill", "#desc", "hello"])
    assert mf.call_args.args[1:] == ("#desc", "hello")


def test_goto_dispatches_to_running_page():
    fake_ctx = MagicMock()
    fake_ctx.pages = [MagicMock()]
    with patch("pa_browser.cli.driver.chrome_running", return_value=True), \
         patch("pa_browser.cli.driver.attach", return_value=_attach_cm(fake_ctx)), \
         patch("pa_browser.cli.driver.goto") as mg:
        _run(["goto", "https://x.test"])
    assert mg.call_args.args[1] == "https://x.test"
