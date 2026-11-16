"""Drive a dedicated, persistent Chrome profile via Playwright.

Why a dedicated profile (not the user's everyday Chrome): since Chrome 136 the
remote-debugging port / CDP is ignored on the *default* user-data-dir, so
automation must run against a *separate* profile. We launch a persistent context
bound to `~/.pa-chrome` (override with $PA_CHROME_DIR) using the system Chrome
channel for a real fingerprint. Log into each site once with `pa-browser login
<url>` and the session persists in that profile across runs.

This replaces the old AppleScript bridge (`chrome.py`, kept as a fallback): it
gives real DOM automation — `fill`/`click`/`wait_for_selector` with Playwright's
auto-waiting — so forms fill and submit reliably, with no "Allow JavaScript from
Apple Events" toggle to babysit.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

_DEFAULT_TIMEOUT_MS = 30_000
_DEFAULT_CDP_PORT = 9222
_DEFAULT_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class BrowserError(RuntimeError):
    """Raised when the persistent Chrome profile can't be driven."""


def resolve_profile_dir(user_data_dir: str | os.PathLike | None = None) -> Path:
    """Where the dedicated automation profile lives (holds the persistent logins)."""
    if user_data_dir:
        return Path(user_data_dir)
    return Path(os.environ.get("PA_CHROME_DIR", str(Path.home() / ".pa-chrome")))


@contextlib.contextmanager
def browser_context(
    *,
    user_data_dir: str | os.PathLike | None = None,
    channel: str | None = "chrome",
    headless: bool = False,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
):
    """Yield a persistent Playwright BrowserContext bound to the dedicated profile.

    channel="chrome" drives the installed Google Chrome (real fingerprint, reuses
    the profile's logged-in sessions). channel=None uses Playwright's bundled
    Chromium — used by the tests and as a fallback when Chrome isn't installed.
    """
    profile = resolve_profile_dir(user_data_dir)
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        kwargs = {"user_data_dir": str(profile), "headless": headless}
        if channel:
            kwargs["channel"] = channel
        try:
            ctx = p.chromium.launch_persistent_context(**kwargs)
        except Exception as exc:  # noqa: BLE001 — Chrome channel may be missing
            if channel:  # retry once with bundled Chromium
                try:
                    ctx = p.chromium.launch_persistent_context(
                        user_data_dir=str(profile), headless=headless
                    )
                except Exception as exc2:  # noqa: BLE001
                    raise BrowserError(str(exc2)) from exc2
            else:
                raise BrowserError(str(exc)) from exc
        ctx.set_default_timeout(timeout_ms)
        try:
            yield ctx
        finally:
            ctx.close()


def active_page(ctx: BrowserContext) -> Page:
    """The context's current page, or a fresh one."""
    return ctx.pages[0] if ctx.pages else ctx.new_page()


def goto(page: Page, url: str, *, wait_until: str = "domcontentloaded") -> Page:
    page.goto(url, wait_until=wait_until)
    return page


def read_text(page: Page, selector: str = "body") -> str:
    """Visible text of the page (or of a selector)."""
    return page.inner_text(selector)


def get_text(page: Page, selector: str) -> str:
    return page.inner_text(selector)


def fill(page: Page, selector: str, value: str) -> None:
    page.fill(selector, value)


def click(page: Page, selector: str) -> None:
    page.click(selector)


def wait_for(page: Page, selector: str) -> None:
    page.wait_for_selector(selector)


def snapshot(page: Page) -> dict:
    """Compact page snapshot for the agent to target elements: url, title, visible
    text, and the interactive elements (inputs/textareas/selects/buttons/links)
    with the attributes needed to build a selector.
    """
    elements = page.eval_on_selector_all(
        "input, textarea, select, button, a[href]",
        """els => els.slice(0, 200).map(e => ({
            tag: e.tagName.toLowerCase(),
            type: e.getAttribute('type') || '',
            name: e.getAttribute('name') || '',
            id: e.id || '',
            placeholder: e.getAttribute('placeholder') || '',
            label: (e.labels && e.labels[0] && e.labels[0].innerText) || '',
            text: (e.innerText || e.value || '').trim().slice(0, 60),
        }))""",
    )
    return {"url": page.url, "title": page.title(), "text": page.inner_text("body"), "elements": elements}


# --- one-shot convenience wrappers (open a context, do one thing, close) ---


def read_url(url: str, **opts) -> str:
    with _page_session(**opts) as page:
        return read_text(goto(page, url))


def snapshot_url(url: str, **opts) -> dict:
    with _page_session(**opts) as page:
        return snapshot(goto(page, url))


def list_tabs(**opts) -> list[dict]:
    with browser_context(**opts) as ctx:
        return [{"index": i + 1, "title": pg.title(), "url": pg.url} for i, pg in enumerate(ctx.pages)]


def login(url: str, *, prompt: Callable[[str], str] = input, **opts) -> None:
    """Open `url` headful in the persistent profile and wait for the user to sign
    in, so the session is captured once and persists for future runs. The user
    types their own credentials in the real Chrome window — automation never
    handles secrets.
    """
    opts.setdefault("headless", False)
    with browser_context(**opts) as ctx:
        goto(active_page(ctx), url, wait_until="load")
        prompt(
            "Sign in in the opened Chrome window, then press Enter here to save the session..."
        )


# --- always-on Chrome: one long-lived visible window we attach to on demand ---
#
# Launch-per-command (browser_context above) is fine for one-shots, but the
# always-on model launches Chrome once with a debug port on the dedicated
# profile and then attaches over CDP for each action, so the window stays
# visible and the user can help with logins / 2FA. Chrome 136 only blocks CDP on
# the *default* user-data-dir, so a non-default profile (~/.pa-chrome) is fine.


def cdp_port() -> int:
    """Port the always-on Chrome exposes CDP on (override $PA_CHROME_CDP_PORT)."""
    return int(os.environ.get("PA_CHROME_CDP_PORT", str(_DEFAULT_CDP_PORT)))


def chrome_binary() -> str:
    """Path to the system Chrome binary (override $PA_CHROME_BINARY)."""
    return os.environ.get("PA_CHROME_BINARY", _DEFAULT_CHROME_BINARY)


def _start_argv(binary: str, profile: str | os.PathLike, port: int) -> list[str]:
    return [
        str(binary),
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def _pidfile(profile: Path) -> Path:
    return profile / ".pa_chrome.pid"


def chrome_running(port: int | None = None) -> bool:
    """True if an always-on Chrome is answering CDP on `port`."""
    port = port or cdp_port()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=1.5
        ) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_chrome(
    *,
    user_data_dir: str | os.PathLike | None = None,
    port: int | None = None,
    binary: str | None = None,
    wait_s: float = 20.0,
) -> int:
    """Launch (or reuse) the always-on visible Chrome on the dedicated profile.

    Idempotent: if CDP is already answering on `port`, returns without spawning a
    second Chrome. Otherwise launches system Chrome detached and waits until CDP
    is up, then returns the port.
    """
    port = port or cdp_port()
    if chrome_running(port):
        return port
    profile = resolve_profile_dir(user_data_dir)
    profile.mkdir(parents=True, exist_ok=True)
    argv = _start_argv(binary or chrome_binary(), profile, port)
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise BrowserError(
            f"Couldn't launch Chrome ({argv[0]}): {exc}. Set $PA_CHROME_BINARY if "
            "Chrome is installed elsewhere."
        ) from exc
    _pidfile(profile).write_text(str(proc.pid))
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if chrome_running(port):
            return port
        time.sleep(0.3)
    raise BrowserError(f"Chrome did not expose CDP on port {port} within {wait_s:g}s")


def stop_chrome(*, user_data_dir: str | os.PathLike | None = None) -> bool:
    """Stop the always-on Chrome we started (via the recorded PID). Returns True
    if a PID was recorded, False if there was nothing to stop.
    """
    profile = resolve_profile_dir(user_data_dir)
    pf = _pidfile(profile)
    if not pf.exists():
        return False
    try:
        os.kill(int(pf.read_text().strip()), signal.SIGTERM)
    except (ValueError, ProcessLookupError, OSError):
        pass
    finally:
        pf.unlink(missing_ok=True)
    return True


@contextlib.contextmanager
def attach(*, port: int | None = None, timeout_ms: int = _DEFAULT_TIMEOUT_MS):
    """Attach to the always-on Chrome over CDP and yield its persistent context.

    Disconnecting (on exit) leaves Chrome running and visible — we only detach
    the automation session, never close the user's window.
    """
    port = port or cdp_port()
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as exc:  # noqa: BLE001 — surface a helpful hint
            raise BrowserError(
                f"Couldn't attach to Chrome on port {port} — run `pa-browser start` "
                f"first ({exc})."
            ) from exc
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        ctx.set_default_timeout(timeout_ms)
        try:
            yield ctx
        finally:
            browser.close()


def current_page(ctx: BrowserContext) -> Page:
    """The front/most-recent page of an attached context (for multi-step flows)."""
    return ctx.pages[-1] if ctx.pages else ctx.new_page()


@contextlib.contextmanager
def _page_session(*, port: int | None = None, **opts):
    """Yield a page to act on: a fresh tab in the always-on Chrome if it's
    running (so the user's logins are used), else a one-shot bundled context.
    """
    if chrome_running(port):
        with attach(port=port) as ctx:
            page = ctx.new_page()
            try:
                yield page
            finally:
                page.close()
    else:
        with browser_context(**opts) as ctx:
            yield active_page(ctx)
