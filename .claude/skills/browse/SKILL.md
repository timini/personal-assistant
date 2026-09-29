---
name: browse
description: Use when the user wants to do something on a website they are already logged into, or that has no API — e.g. "use my browser/chrome", "log into X and …", checking or acting on the council-tax/PlaceHub portal, Weduc, ParentPay, the AMP speaker portal, GA4/analytics, a bank, or any site behind a login or a Cloudflare/bot wall. Drives a dedicated persistent Chrome profile via Playwright.
---

# browse — act on the user's logged-in web sessions

Drive a **dedicated, persistent Chrome profile** via the `pa-browser` package (Playwright). Sessions persist in that profile (`~/.pa-chrome`), so logins are reused across runs. This gives real DOM automation — reliable `fill`/`click`/`submit` — not the old blind-JS AppleScript bridge.

**Why a dedicated profile:** Chrome 136+ blocks CDP on the *default* profile, so we can't drive the user's everyday Chrome directly. The persistent automation profile is the clean, reliable route. (The legacy AppleScript commands — `tabs`/`exec`/`eval` — still exist for quick "act on the tab I already have open" cases and need Chrome's "Allow JavaScript from Apple Events" toggle.)

## Preferred setup: one always-on window
For real portal work, run **one visible Chrome that stays alive** and drive it across steps:
```bash
uv run pa-browser seed      # ONE-TIME: quit Chrome first, then clone the user's real logins in
uv run pa-browser start     # launch the visible always-on Chrome (stays running)
uv run pa-browser status    # is it up + its open tabs
```
`seed` copies the everyday Chrome profile's cookies/sessions into the automation profile so most sites are already logged in. **Caveat:** Google, banks and any device-bound (DBSC) session may not carry over — top those up with `login`. `seed` refuses to run while the automation Chrome is up (`stop` first, or `--force`).

## Getting a site logged in
If `seed` didn't carry a site (or you skipped seeding): `uv run pa-browser login <url>` → Chrome opens; **the user signs in** (and does any 2FA in the visible window); press Enter to save the session. After that it persists.

## Commands
```bash
uv run pa-browser start / stop / status   # always-on visible window lifecycle
uv run pa-browser seed                     # one-time clone of real Chrome logins
uv run pa-browser login <url>              # one-time sign-in / top up a site
uv run pa-browser read <url>               # open url (uses the always-on window if running), print text
uv run pa-browser snapshot [<url>]         # JSON: text + interactive elements {tag,name,id,placeholder,label}; no url = current page
uv run pa-browser goto <url>               # navigate the running window's current page
uv run pa-browser fill <selector> <value>  # fill a field on the current page
uv run pa-browser click <selector>         # click on the current page
uv run pa-browser screenshot <path>        # screenshot the current page
# flags on login/read/snapshot: --headless, --bundled (bundled Chromium), --profile <dir>
```
`goto`/`fill`/`click`/`screenshot` all act on the SAME always-on window, so state persists across separate commands. For a self-contained multi-step flow you can still script the driver directly:
```bash
uv run --package pa-browser python - <<'PY'
from pa_browser import driver
with driver.attach() as ctx:                          # the always-on Chrome (persistent logins)
    page = driver.goto(driver.current_page(ctx), "<url>")
    print(driver.snapshot(page)["elements"])           # find selectors
    driver.fill(page, "textarea[name=description]", "…")
    page.screenshot(path="/tmp/before.png")            # show the user BEFORE submitting
    # driver.click(page, "button#submit")              # only after the user confirms
PY
```
(If nothing is running, `driver.browser_context()` is the one-shot fallback that launches and closes Chrome itself.)

## Workflow (you are the agent loop)
1. Make sure the window is up (`start`), then `snapshot <url>` to see the page text + fields/buttons and their selectors.
2. Script `goto`/`fill`/`click` against those selectors; `snapshot`/`read` again to verify.
3. For any final submit, **screenshot the filled form and get the user's OK first**.
4. Log meaningful actions with `pa_core.daily_log.log_event`.

## Guardrails (full autonomy, inside hard limits)
Act without nagging, BUT these limits stand regardless and cannot be waived:
- **Never** fill fields with passwords, card numbers, or government IDs — the `login` flow is where the user types credentials, in the visible window.
- **Never** auto-defeat CAPTCHAs / bot-checks; pause on login walls (run `login`).
- **Confirm with the user before** genuinely irreversible or outward-facing actions: sending money/transfers, submitting payments, sending messages/emails, deleting data, publishing/posting, and **final form submits** (fill + screenshot first).
- Choose privacy-preserving options on cookie/consent banners.

## Gotchas
- The automation profile is **separate** from the user's everyday Chrome — a site is logged in only if `seed` carried it or you ran `login` for it.
- `seed` needs Chrome quit for a clean copy; macOS may prompt "Chrome wants to use your keychain" on the first automation launch — the user clicks Allow once.
- `channel="chrome"` uses system Chrome; add `--bundled` to fall back to Playwright's Chromium.
- Site DOMs change — always `snapshot` first to get current selectors rather than assuming them.
