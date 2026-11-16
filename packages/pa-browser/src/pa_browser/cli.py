"""CLI entry point for pa-browser.

Primary path (Playwright, dedicated persistent Chrome profile): `login`, `read`,
`snapshot`. Log in once per site, sessions persist. For multi-step form flows,
script against `pa_browser.driver` directly (see AGENTS.md).

Legacy path (AppleScript → your real, running Chrome): `tabs`, `exec`, `eval`.
Kept for quick "act on the tab I already have open" cases; needs Chrome's
"Allow JavaScript from Apple Events" toggle.
"""

import argparse
import json
import sys

from pa_browser import chrome, driver, seed


def _browser_opts(args) -> dict:
    opts = {"headless": bool(getattr(args, "headless", False))}
    if getattr(args, "bundled", False):
        opts["channel"] = None  # Playwright's bundled Chromium instead of system Chrome
    if getattr(args, "profile", None):
        opts["user_data_dir"] = args.profile
    return opts


# --- primary (Playwright) ---


def cmd_login(args):
    driver.login(args.url, **_browser_opts(args))
    print("Session saved to the automation profile.")


def cmd_read(args):
    print(driver.read_url(args.url, **_browser_opts(args)))


def cmd_snapshot(args):
    if getattr(args, "url", None):
        print(json.dumps(driver.snapshot_url(args.url, **_browser_opts(args)), indent=2))
    else:  # snapshot the current page of the always-on Chrome
        print(json.dumps(_on_current_page(driver.snapshot), indent=2))


# --- always-on Chrome: lifecycle + seed + driving the visible window ---


def cmd_start(args):
    port = driver.start_chrome(
        port=getattr(args, "port", None), user_data_dir=getattr(args, "profile", None)
    )
    print(f"Automation Chrome is up (CDP port {port}). The visible window is ready to drive.")


def cmd_stop(args):
    stopped = driver.stop_chrome(user_data_dir=getattr(args, "profile", None))
    print("Stopped the automation Chrome." if stopped else "Nothing to stop (no recorded PID).")


def cmd_status(args):
    port = driver.cdp_port()
    if not driver.chrome_running(port):
        print("Automation Chrome: not running. Start it with `pa-browser start`.")
        return
    with driver.attach(port=port) as ctx:
        tabs = [{"index": i + 1, "title": p.title(), "url": p.url} for i, p in enumerate(ctx.pages)]
    print(f"Automation Chrome: running (CDP port {port}), {len(tabs)} tab(s).")
    for t in tabs:
        print(f"  [{t['index']}] {t['title'][:55]}\n      {t['url']}")


def cmd_seed(args):
    copied = seed.seed_profile(
        src_profile=getattr(args, "from_profile", None), force=getattr(args, "force", False)
    )
    print(f"Seeded {len(copied)} item(s): {', '.join(copied) or '(none found)'}")
    print("Run `pa-browser start` next. Google/bank may still need a one-time `pa-browser login`.")


def _on_current_page(fn):
    """Run fn(page) against the front page of the always-on Chrome."""
    if not driver.chrome_running():
        raise driver.BrowserError(
            "Automation Chrome isn't running — run `pa-browser start` first."
        )
    with driver.attach() as ctx:
        return fn(driver.current_page(ctx))


def cmd_goto(args):
    _on_current_page(lambda p: driver.goto(p, args.url, wait_until="load"))
    print(f"Navigated to {args.url}")


def cmd_fill(args):
    _on_current_page(lambda p: driver.fill(p, args.selector, args.value))
    print(f"Filled {args.selector}")


def cmd_click(args):
    _on_current_page(lambda p: driver.click(p, args.selector))
    print(f"Clicked {args.selector}")


def cmd_screenshot(args):
    _on_current_page(lambda p: p.screenshot(path=args.path))
    print(f"Saved screenshot to {args.path}")


# --- legacy (AppleScript → real Chrome) ---


def _load_js(args) -> str:
    if getattr(args, "js_file", None):
        with open(args.js_file) as f:
            return f.read()
    return args.js


def cmd_tabs(args):
    tabs = chrome.list_tabs()
    if args.json:
        print(json.dumps(tabs, indent=2))
        return
    if not tabs:
        print("No open tabs (is Chrome running?)")
    for t in tabs:
        loading = " (loading)" if t.get("loading") else ""
        print(f"[{t['window']}.{t['index']}] {t['title'][:55]}{loading}\n      {t['url']}")


def cmd_exec(args):
    print(chrome.exec_js(args.url, _load_js(args), async_=args.async_, timeout=args.wait))


def cmd_eval(args):
    print(chrome.eval_tab(args.tab, _load_js(args), async_=args.async_, timeout=args.wait))


def main():
    parser = argparse.ArgumentParser(
        prog="pa-browser",
        description="Drive a dedicated persistent Chrome profile via Playwright "
        "(login/read/snapshot). Legacy AppleScript commands (tabs/exec/eval) act on "
        "your real running Chrome.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_browser_flags(p):
        p.add_argument("--headless", action="store_true", help="Run without a visible window")
        p.add_argument("--bundled", action="store_true",
                       help="Use Playwright's bundled Chromium instead of system Chrome")
        p.add_argument("--profile", help="Override the profile dir (default ~/.pa-chrome or $PA_CHROME_DIR)")

    login_p = sub.add_parser("login", help="One-time sign-in to a site in the automation profile")
    login_p.add_argument("url")
    add_browser_flags(login_p)

    read_p = sub.add_parser("read", help="Open a URL (persistent session) and print the page text")
    read_p.add_argument("url")
    add_browser_flags(read_p)

    snap_p = sub.add_parser("snapshot", help="Print JSON: page text + interactive elements (for targeting)")
    snap_p.add_argument("url", nargs="?", help="URL to open; omit to snapshot the running window's current page")
    add_browser_flags(snap_p)

    # always-on Chrome lifecycle
    start_p = sub.add_parser("start", help="Launch the always-on visible Chrome on the automation profile")
    start_p.add_argument("--port", type=int, help=f"CDP port (default {driver.cdp_port()} / $PA_CHROME_CDP_PORT)")
    start_p.add_argument("--profile", help="Override the profile dir (default ~/.pa-chrome or $PA_CHROME_DIR)")

    stop_p = sub.add_parser("stop", help="Stop the always-on Chrome we started")
    stop_p.add_argument("--profile", help="Override the profile dir")

    sub.add_parser("status", help="Show whether the always-on Chrome is running and its open tabs")

    seed_p = sub.add_parser("seed", help="Clone your real Chrome logins into the automation profile (one-time)")
    seed_p.add_argument("--from-profile", dest="from_profile",
                        help="Source Chrome profile name (default: auto-detect last used)")
    seed_p.add_argument("--force", action="store_true",
                        help="Copy even if the automation Chrome appears to be running")

    # driving the always-on window (act on its current page, state persists across calls)
    goto_p = sub.add_parser("goto", help="Navigate the running window's current page to a URL")
    goto_p.add_argument("url")

    fill_p = sub.add_parser("fill", help="Fill a field on the running window's current page")
    fill_p.add_argument("selector")
    fill_p.add_argument("value")

    click_p = sub.add_parser("click", help="Click an element on the running window's current page")
    click_p.add_argument("selector")

    shot_p = sub.add_parser("screenshot", help="Screenshot the running window's current page")
    shot_p.add_argument("path")

    tabs_p = sub.add_parser("tabs", help="[legacy] List open tabs of your real running Chrome (AppleScript)")
    tabs_p.add_argument("--json", action="store_true")

    exec_p = sub.add_parser("exec", help="[legacy] Open a URL in real Chrome, run a JS payload (AppleScript)")
    exec_p.add_argument("url")
    ge = exec_p.add_mutually_exclusive_group(required=True)
    ge.add_argument("--js")
    ge.add_argument("--js-file")
    exec_p.add_argument("--async", dest="async_", action="store_true")
    exec_p.add_argument("--wait", type=int, default=30)

    eval_p = sub.add_parser("eval", help="[legacy] Run JS in an already-open real-Chrome tab (1-based index)")
    eval_p.add_argument("tab", type=int)
    gv = eval_p.add_mutually_exclusive_group(required=True)
    gv.add_argument("--js")
    gv.add_argument("--js-file")
    eval_p.add_argument("--async", dest="async_", action="store_true")
    eval_p.add_argument("--wait", type=int, default=30)

    args = parser.parse_args()
    handlers = {
        "login": cmd_login, "read": cmd_read, "snapshot": cmd_snapshot,
        "start": cmd_start, "stop": cmd_stop, "status": cmd_status, "seed": cmd_seed,
        "goto": cmd_goto, "fill": cmd_fill, "click": cmd_click, "screenshot": cmd_screenshot,
        "tabs": cmd_tabs, "exec": cmd_exec, "eval": cmd_eval,
    }
    try:
        handlers[args.command](args)
    except driver.BrowserError as e:
        print(f"Browser error: {e}", file=sys.stderr)
        print("Tip: run `pa-browser login <url>` once to sign in; make sure Google Chrome is installed "
              "(or add --bundled to use Playwright's Chromium).", file=sys.stderr)
        sys.exit(1)
    except chrome.ChromeError as e:
        print(f"Chrome (legacy) error: {e}", file=sys.stderr)
        sys.exit(1)
    except seed.SeedError as e:
        print(f"Seed error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
