"""Drive the user's real, logged-in Google Chrome via AppleScript/JXA (osascript).

Why this and not CDP / the Chrome extension: since Chrome 136 the remote-debugging
port is ignored on the real (default) profile, and a separate automation Chromium
can't decrypt the user's cookies (macOS Keychain) and trips bot-walls. Running JS
*inside the user's actual Chrome* via AppleScript reuses their live logged-in
sessions. Requires Chrome → View → Developer → "Allow JavaScript from Apple Events".

Payloads are passed as base64 (decoded in-page with atob+eval) to avoid AppleScript
quote-escaping. Async results come back via a document.title channel (the JXA can't
await page promises): the page sets `document.title = PA_MARKER + JSON`, which we poll.
"""

import base64
import json

from pa_core.cli_runner import run_cli

PA_MARKER = "__PA__:"
_DEFAULT_TIMEOUT = 30  # seconds, used for both page-load wait and async title poll


class ChromeError(RuntimeError):
    """Raised when Chrome can't be controlled or a payload fails."""


def _osascript(script: str) -> str:
    """Run a JXA script via osascript and return trimmed stdout (raising on failure)."""
    result = run_cli(["osascript", "-l", "JavaScript", "-e", script], check=False)
    if getattr(result, "returncode", 0) != 0:
        err = (getattr(result, "stderr", "") or "osascript failed").strip()
        if "-1708" in err or "Message not understood" in err:
            raise ChromeError(
                "Chrome won't run JavaScript from Apple Events. Tick it: "
                "Chrome menu bar > View > Developer > 'Allow JavaScript from Apple Events'. "
                "It takes effect immediately (no relaunch) and RESETS to off whenever Chrome "
                "restarts, so re-tick it if it stops working."
            )
        raise ChromeError(err)
    out = (getattr(result, "stdout", "") or "").strip()
    if out.startswith("ERR:"):
        raise ChromeError(out[len("ERR:"):].strip())
    return out


def _payload_literal(js: str, *, raw: bool) -> str:
    """JS to run in the page, as a JXA string literal.

    raw=True embeds the JS directly (used for simple, safe reads like innerText);
    raw=False wraps it as eval(atob("<base64>")) so arbitrary payloads need no escaping.
    """
    if raw:
        return json.dumps(js)
    b64 = base64.b64encode(js.encode()).decode()
    # decodeURIComponent(escape(atob(...))) makes the base64 round-trip UTF-8 safe
    # (plain atob returns raw bytes, mangling multi-byte chars like bullets/curly quotes).
    return json.dumps(f'eval(decodeURIComponent(escape(atob("{b64}"))))')


def _return_block(async_: bool, *, close: bool, timeout: int) -> str:
    close_stmt = "try { tab.close(); } catch (_) {}" if close else ""
    if async_:
        return f"""
  var out = null, w2 = 0;
  while (w2 < {timeout}) {{
    var ti = tab.title();
    if (ti && ti.indexOf("{PA_MARKER}") === 0) {{ out = ti.substring({len(PA_MARKER)}); break; }}
    app.delay(0.3); w2 += 0.3;
  }}
  {close_stmt}
  return out === null ? "ERR:timeout waiting for result" : out;
"""
    return f"""
  {close_stmt}
  return (res === null || res === undefined) ? "" : (typeof res === "string" ? res : JSON.stringify(res));
"""


def _open_exec_script(url: str, js: str, *, raw: bool, async_: bool, timeout: int) -> str:
    return f"""(function(){{
  var app = Application.currentApplication(); app.includeStandardAdditions = true;
  var c = Application("Google Chrome");
  if (!c.running()) return "ERR:Chrome not running";
  if (c.windows.length === 0) return "ERR:No Chrome window open";
  var win = c.windows[0];
  var tab = c.Tab({{url: {json.dumps(url)}}});
  win.tabs.push(tab);                       // hold the reference we created (reliable target)
  try {{ win.activeTabIndex = win.tabs.length; }} catch (_) {{}}
  app.delay(0.5);
  var waited = 0;
  while (tab.loading() && waited < {timeout}) {{ app.delay(0.3); waited += 0.3; }}
  var res;
  try {{ res = tab.execute({{javascript: {_payload_literal(js, raw=raw)}}}); }}
  catch (e) {{ try {{ tab.close(); }} catch (_) {{}} return "ERR:execjs:" + e.message; }}
{_return_block(async_, close=True, timeout=timeout)}}})();"""


def _eval_script(index: int, js: str, *, async_: bool, timeout: int) -> str:
    return f"""(function(){{
  var app = Application.currentApplication(); app.includeStandardAdditions = true;
  var c = Application("Google Chrome");
  if (!c.running()) return "ERR:Chrome not running";
  if (c.windows.length === 0) return "ERR:No Chrome window open";
  var win = c.windows[0];
  if (win.tabs.length < {index}) return "ERR:no tab at index {index}";
  var tab = win.tabs[{index} - 1];
  var res;
  try {{ res = tab.execute({{javascript: {_payload_literal(js, raw=False)}}}); }}
  catch (e) {{ return "ERR:execjs:" + e.message; }}
{_return_block(async_, close=False, timeout=timeout)}}})();"""


def list_tabs() -> list[dict]:
    """Return all open tabs of every Chrome window: [{window, index, title, url, loading}]."""
    script = """(function(){
  var c = Application("Google Chrome");
  if (!c.running()) return "ERR:Chrome not running";
  var out = [];
  var ws = c.windows;
  for (var i = 0; i < ws.length; i++) {
    var ts = ws[i].tabs;
    for (var j = 0; j < ts.length; j++) {
      out.push({window: i, index: j + 1, title: ts[j].title(), url: ts[j].url(), loading: ts[j].loading()});
    }
  }
  return JSON.stringify(out);
})();"""
    out = _osascript(script)
    return json.loads(out) if out else []


def read_url(url: str, *, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """Open a new tab at url (reusing the live session), return document.body.innerText, close it."""
    return _osascript(_open_exec_script(url, "document.body.innerText", raw=True, async_=False, timeout=timeout))


def exec_js(url: str, js: str, *, async_: bool = False, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """Open a new tab at url, run a JS payload, return its result, close the tab.

    Sync (default): the result is the payload's last expression value.
    async_=True: the payload must set `document.title = PA_MARKER + JSON.stringify(result)`
    (used for fetch/await); we poll the title and return the JSON.
    """
    return _osascript(_open_exec_script(url, js, raw=False, async_=async_, timeout=timeout))


def eval_tab(index: int, js: str, *, async_: bool = False, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """Run a JS payload in an already-open tab (1-based index in the front window). Doesn't open/close."""
    return _osascript(_eval_script(index, js, async_=async_, timeout=timeout))
