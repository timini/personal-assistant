"""Tests for the Playwright driver — exercised against a local HTML form fixture
using Playwright's bundled Chromium (headless, temp profile), so no system Chrome
or logged-in session is required.
"""

import pytest

from pa_browser import driver

FIXTURE_HTML = """<!doctype html><html><head><title>WF Report</title></head><body>
<h1 id="hd">Report a problem</h1>
<form id="f">
  <label for="desc">Description</label>
  <input name="desc" id="desc" placeholder="Describe the issue">
  <input name="postcode" id="postcode" placeholder="Postcode">
  <button type="button" id="go"
    onclick="document.getElementById('out').innerText='submitted:'+document.getElementById('desc').value">
    Submit
  </button>
</form>
<div id="out"></div>
</body></html>"""


@pytest.fixture
def fixture_url(tmp_path):
    f = tmp_path / "form.html"
    f.write_text(FIXTURE_HTML)
    return f.as_uri()


@pytest.fixture
def opts(tmp_path):
    # bundled Chromium + throwaway profile so tests need no system Chrome / login
    return {"user_data_dir": tmp_path / "profile", "channel": None, "headless": True}


def test_read_text(fixture_url, opts):
    with driver.browser_context(**opts) as ctx:
        page = driver.active_page(ctx)
        driver.goto(page, fixture_url)
        assert "Report a problem" in driver.read_text(page)


def test_fill_click_read(fixture_url, opts):
    with driver.browser_context(**opts) as ctx:
        page = driver.active_page(ctx)
        driver.goto(page, fixture_url)
        driver.fill(page, "#desc", "illegal waste site")
        driver.click(page, "#go")
        assert driver.get_text(page, "#out") == "submitted:illegal waste site"


def test_snapshot_lists_inputs(fixture_url, opts):
    with driver.browser_context(**opts) as ctx:
        page = driver.active_page(ctx)
        driver.goto(page, fixture_url)
        snap = driver.snapshot(page)
        names = [e["name"] for e in snap["elements"]]
        assert "desc" in names and "postcode" in names
        assert snap["title"] == "WF Report"


def test_read_url_oneshot(fixture_url, opts):
    assert "Report a problem" in driver.read_url(fixture_url, **opts)


def test_profile_dir_default(monkeypatch):
    monkeypatch.setenv("PA_CHROME_DIR", "/tmp/pa-chrome-test")
    assert driver.resolve_profile_dir().as_posix() == "/tmp/pa-chrome-test"


# --- always-on Chrome (start / attach / lifecycle) ---


def test_cdp_port_default(monkeypatch):
    monkeypatch.delenv("PA_CHROME_CDP_PORT", raising=False)
    assert driver.cdp_port() == 9222


def test_cdp_port_from_env(monkeypatch):
    monkeypatch.setenv("PA_CHROME_CDP_PORT", "9333")
    assert driver.cdp_port() == 9333


def test_start_argv_has_profile_and_port():
    argv = driver._start_argv("/Chrome", "/tmp/prof", 9222)
    assert argv[0] == "/Chrome"
    assert "--user-data-dir=/tmp/prof" in argv
    assert "--remote-debugging-port=9222" in argv


def test_chrome_running_true(monkeypatch):
    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(driver.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert driver.chrome_running(9222) is True


def test_chrome_running_false(monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(driver.urllib.request, "urlopen", _boom)
    assert driver.chrome_running(9222) is False


def test_start_chrome_is_idempotent_when_already_running(monkeypatch):
    monkeypatch.setattr(driver, "chrome_running", lambda *a, **k: True)
    called = []
    monkeypatch.setattr(driver.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert driver.start_chrome(port=9222) == 9222
    assert not called  # did not spawn a second Chrome


def test_attach_connects_over_cdp(monkeypatch):
    calls = {}

    class _Ctx:
        def set_default_timeout(self, t):
            calls["timeout"] = t

    class _Browser:
        contexts = [_Ctx()]

        def close(self):
            calls["closed"] = True

    class _Chromium:
        def connect_over_cdp(self, url):
            calls["url"] = url
            return _Browser()

    class _P:
        chromium = _Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(driver, "sync_playwright", lambda: _P())
    with driver.attach(port=9333) as ctx:
        assert isinstance(ctx, _Ctx)
    assert calls["url"] == "http://127.0.0.1:9333"
    assert calls["closed"] is True  # disconnects CDP but leaves Chrome running
