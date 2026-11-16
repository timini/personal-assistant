# pa-browser — Package Instructions

## Goal
**Act reliably on the user's logged-in web sessions.** Drive a dedicated, persistent
Chrome profile via **Playwright** so tasks (council-tax/PlaceHub portal, Weduc/ParentPay,
AMP speaker portal, GA4, bank) get real DOM automation — fill/click/submit that actually
works. The coding agent is the brain; Chrome is the hands.

## Why Playwright + a *dedicated* profile (not the user's everyday Chrome)
- Since **Chrome 136** the remote-debugging port / CDP is ignored on the **default**
  user-data-dir, so you cannot drive the user's everyday Chrome over CDP.
- The fix is a **separate persistent profile** (`~/.pa-chrome`, override `$PA_CHROME_DIR`).
  You log into each site **once** (`pa-browser login <url>`) and the session persists in
  that profile across runs — no repeated logins, no cookie-decryption hacks.
- Playwright gives auto-waiting `fill`/`click`/`wait_for_selector` + a `snapshot` of the
  page's interactive elements, so forms fill and submit accurately and fast.
- The old AppleScript bridge (`chrome.py`) is kept as a **legacy fallback** only — it relied
  on Chrome's "Allow JavaScript from Apple Events" toggle (silently resets on restart), had
  no real element model, and could not reliably fill forms.

## Two ways to run
1. **Always-on window (preferred for real work).** `pa-browser start` launches ONE visible
   Chrome on the dedicated profile with a CDP debug port, and it stays alive. The agent
   attaches over CDP for each action (`driver.attach()`), so state persists across commands
   and the user can watch and step in for logins / 2FA. `pa-browser stop` / `status` manage it.
2. **One-shot (fallback).** `read` / `snapshot` (and scripting `browser_context()`) launch and
   close Chrome per command. If an always-on window is running, `read`/`snapshot` automatically
   act in it (a fresh tab) so the user's logins are used.

## Prerequisites (one-time)
1. `uv sync` (installs Playwright), then `uv run --package pa-browser python -m playwright install chromium`
   (only needed if not using system Chrome).
2. **Seed logins once (optional but recommended):** quit Chrome, then `uv run pa-browser seed`
   clones the everyday Chrome profile's cookies/sessions into `~/.pa-chrome/Default`, so most
   sites are already signed in. On macOS the shared "Chrome Safe Storage" Keychain key lets the
   copied cookies decrypt in the automation profile. **Caveat:** Google, banks and any site using
   device-bound session credentials (DBSC) may not survive the copy — top those up with `login`.
3. `uv run pa-browser login <url>` for any site the seed didn't carry → the user signs in in the
   opened Chrome window; the session is saved to `~/.pa-chrome` and reused thereafter.

## API (`pa_browser.driver`)
- `browser_context(*, user_data_dir=None, channel="chrome", headless=False, timeout_ms=30000)`
  — context manager yielding a persistent Playwright `BrowserContext`. `channel="chrome"`
  drives system Chrome (real fingerprint + persistent logins); `channel=None` uses bundled
  Chromium (tests / no-Chrome fallback).
- `active_page(ctx)`, `goto(page, url)`, `read_text(page[, selector])`, `get_text(page, sel)`,
  `fill(page, sel, value)`, `click(page, sel)`, `wait_for(page, sel)`.
- `snapshot(page)` → `{url, title, text, elements[]}` where each element has
  `{tag, type, name, id, placeholder, label, text}` — use this to pick selectors.
- One-shots: `read_url(url, **opts)`, `snapshot_url(url, **opts)`, `list_tabs(**opts)`.
- `login(url, *, prompt=input, **opts)` — headful sign-in; the **user** types credentials.
- `resolve_profile_dir()`, `BrowserError`.

**Always-on lifecycle (`pa_browser.driver`):**
- `start_chrome(*, user_data_dir=None, port=None, binary=None)` — launch (or reuse) the visible
  Chrome; idempotent. `stop_chrome()`, `chrome_running(port=None)`, `cdp_port()`, `chrome_binary()`.
- `attach(*, port=None)` — context manager yielding the running Chrome's persistent context over
  CDP; on exit it disconnects but leaves Chrome open. `current_page(ctx)` = its front tab.
- Multi-step flows against the live window: `with driver.attach() as ctx: page = driver.current_page(ctx); driver.fill(...); page.screenshot(...); driver.click(...)`.

**Seeding (`pa_browser.seed`):** `seed_profile(*, src_user_data_dir=None, src_profile=None, dest_user_data_dir=None, force=False)`,
`detect_source_profile(dir)`, `real_user_data_dir()`, `SeedError`. Refuses to run while the
automation Chrome is up (pass `force=True` to override).

**Multi-step form flows** (fill several fields → submit) need ONE context held across the
steps, so script them directly, e.g.:
```bash
uv run --package pa-browser python - <<'PY'
from pa_browser import driver
with driver.browser_context() as ctx:      # real Chrome, persistent logins
    page = driver.goto(driver.active_page(ctx), "https://placehub.walthamforest.gov.uk/...")
    print(driver.snapshot(page)["elements"])   # find the field selectors
    driver.fill(page, "textarea[name=description]", "...report text...")
    page.screenshot(path="/tmp/before-submit.png")   # PAUSE: show the user before submitting
    # driver.click(page, "button#submit")            # only after user confirms
PY
```

## CLI
```
pa-browser seed              # one-time: clone real Chrome logins into the automation profile
pa-browser start             # launch the always-on visible Chrome (stays alive)
pa-browser status            # is it running + its open tabs
pa-browser stop              # stop the always-on Chrome we started
pa-browser login <url>       # one-time sign-in into the automation profile (top up a site)
pa-browser read <url>        # print page text (uses the always-on window if running)
pa-browser snapshot [<url>]  # JSON: page text + interactive elements; no url = current page
pa-browser goto <url>        # navigate the running window's current page
pa-browser fill <sel> <val>  # fill a field on the running window's current page
pa-browser click <sel>       # click on the running window's current page
pa-browser screenshot <path> # screenshot the running window's current page
pa-browser tabs              # [legacy] list your REAL running Chrome's tabs (AppleScript)
pa-browser exec <url> --js…  # [legacy] run JS in real Chrome (AppleScript)
pa-browser eval <tab> --js…  # [legacy] run JS in an already-open real-Chrome tab
```
The `goto`/`fill`/`click`/`screenshot` verbs drive the SAME always-on window, so state persists
across separate commands (goto → fill → screenshot → confirm → click). They error if it isn't
running — `pa-browser start` first. Flags on login/read/snapshot: `--headless`, `--bundled`
(bundled Chromium), `--profile <dir>`.
Used by the shared **browse** skill (`.claude/skills/browse/SKILL.md`, mirrored to `.agents/skills/browse`).

## Guardrails
Never inject/type passwords, card numbers or IDs via automation — the `login` flow relies on
the **user** typing credentials in the headful window. Never bypass CAPTCHAs. Confirm before
irreversible/outward actions (payments, sends, publishing, and **final form submits** — fill +
screenshot first, submit only after the user confirms).

## Caveats
- Uses a separate profile from the user's everyday Chrome (one-time login per site).
- `channel="chrome"` needs Google Chrome installed; falls back to bundled Chromium.
- Personal-tool grade; site DOMs change, so selectors may need adjusting — use `snapshot` first.
