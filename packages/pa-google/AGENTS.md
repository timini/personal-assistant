# pa-google — Package Instructions

## Goal
**Inbox Zero.** The inbox should be empty at all times.

## Email Triage Rules

> **Principle: No email exists in isolation.** Always check if an email relates to something already tracked in Notion before deciding how to handle it. Extract every date, deadline, link, and action item — don't leave value on the table.

### Incremental triage — only handle what's NEW

Triage works from the **last time triage was run**, so you don't re-surface mail already dealt with:

1. **Start** every triage with `uv run pa-google emails --since-last` — this fetches only mail received since the last triage (using a stored cursor + Gmail `after:`). On the very first run (no cursor yet) it falls back to the full inbox and says so.
2. Triage as below.
3. **End** the pass with `uv run pa-google emails --mark-triaged` — stamps "now" as the new cursor.

(Plain `uv run pa-google emails` still pulls the full inbox if you ever need everything. Cursor is stored in `activity/.state.json` under `last_email_triage`. Caveat: the cursor is stamped when you mark done, so anything arriving mid-session is picked up next run.)

### Triage steps

1. Fetch new inbox emails with `--since-last` (read + unread) — not just unread
2. **Cross-reference each email against Notion tasks/projects** before categorising:
   - Search for related tasks by keyword (sender name, subject terms, project names)
   - If a related task exists, extract and act on ALL information in the email:
     - **Dates/events** → create calendar events (use Family Calendar for personal, primary for work)
     - **Deadlines** → update task due dates or create sub-tasks
     - **Links** (fundraising pages, sign-up forms, resources) → add to task notes
     - **Action items** → create sub-tasks or update existing task notes
     - **Key contacts/details** → add to task notes
   - An email that seems like "just info" on its own may be critical context for an existing task
3. **Then** categorise and act on each email:
   - **Noise** (delivery updates, parking receipts, generic notifications with no task relevance) → archive
   - **Quick action** (pay a bill, RSVP, short reply) → do it, then archive
   - **Needs follow-up** → create Notion task with context + email link, then archive
   - **Time-sensitive** → flag to user
4. If an email has a matching Notion task, archive it immediately
5. Include Gmail links in Notion task notes: `https://mail.google.com/mail/u/0/#inbox/<message_id>`

## Gmail Gotchas

### Archive by THREAD, not message
ALWAYS use `gws gmail users threads modify` — NOT `messages modify`. Gmail UI shows threads. Use `archive_email()` from `pa_google.gmail`.

### gws CLI syntax
- Resources are space-separated: `users messages` not `users.messages`
- Parameters: `--params '<json>'`, request body: `--json '<json>'`
- gws prints preamble before JSON — `parse_json_output()` handles this

### Searching Gmail — include trash and spam by default
By default, `gws gmail users messages list` only returns mail from the **inbox + archive**. Items in **Trash** and **Spam** are excluded unless you explicitly opt in.

When searching for an email and not finding it (e.g. order confirmations, receipts, anything the user expected to receive), **always re-run the search including Trash and Spam** before concluding it's not there. Users routinely auto-delete or accidentally trash receipts that turn out to be load-bearing later.

Two ways to do this:
- Add `in:all` to your query string: `'q': 'Brisks in:all'`
- Or pass `"includeSpamTrash": true` in the params

Example:
```bash
gws gmail users messages list --params '{"userId":"me","q":"Brisks in:all","maxResults":15}'
```

Default search flow when looking for a missing email:
1. Search inbox+archive
2. If nothing relevant → search again with `in:all`
3. Only declare "not found" after both have come up empty

## Email Attachments → Google Drive
1. Save attachments using `gws gmail users messages attachments get`
2. Upload to Drive with `gws drive files create --upload <path>`
3. Organise into project folders: `PA/<Project>/<Sender or Context>/`
4. Link Drive files in relevant Notion project page

## Sending Emails

**Never ask "shall I send it?" — always create a Gmail draft and provide the review link.**

When composing any email on the user's behalf, use the `create_draft()` helper:
```python
from pa_google.gmail import create_draft
result = create_draft(
    to="recipient@example.com",
    subject="Re: Thread subject",
    body="Email body text",
    thread_id="<thread_id>",  # optional, for replies
)
print(result["link"])  # link for user to review
```

**Do NOT build raw RFC 2822 messages manually** — `create_draft()` uses `email.mime` for proper encoding and auto-recovers if Gmail silently trashes the draft (a known Gmail API quirk with malformed headers).

**NEVER use the Gmail MCP tool (`mcp__claude_ai_Gmail__gmail_create_draft`)** — it has a known bug where using `threadId` produces drafts with empty bodies. Always use `pa_google.gmail.create_draft()` which handles encoding, trash detection, and recovery correctly.

## Research Tasks → Google Docs

When doing research (supplier comparisons, costings, options analysis, etc.), **always save the output as a Google Doc** so it persists across conversations.

1. **Create a Google Doc** with the research findings using `gws docs documents create`
2. **Organise in Drive** under the relevant project folder: `PA/<Project>/Research/`
   - e.g. `PA/House Renovation/Research/Door Suppliers Comparison.gdoc`
   - e.g. `PA/Garden/Research/Tree Costings.gdoc`
3. **Link the Doc** in the relevant Notion task notes so it's easy to find later
4. **Structure the doc clearly** — use headings, tables, pros/cons, pricing. Make it actionable.

Research that isn't saved is research wasted. The user should never have to ask the assistant to redo work from a previous session.

## Calendar
- Use `get_all_todays_events()` / `get_all_upcoming_events()` for multi-calendar support
- Use `get_todays_events()` / `get_upcoming_events()` for single-calendar queries
- When creating events, check `user-instructions.md` at repo root for which calendar to use and who to invite

## Work Outlook → Google "Day Job" sync (`outlook.py` + `outlook_sync.py`)

Mirrors the configured work Outlook calendar into the Google "Day Job" calendar so work events appear in the morning context/briefings. Runs automatically in `pa-core checkin`; standalone: `uv run pa-google calendar-sync-outlook [--days N]`.

**How it works:** `get_outlook_events()` reads the **Legacy** Microsoft Outlook desktop app via AppleScript (`osascript`) — picking the work calendar by content (busiest in the window), when multiple locally synced calendars exist. `sync_outlook_to_google()` then does a one-way idempotent mirror: each synced Google event is stamped `extendedProperties.private.syncedFrom=outlook` + an `outlookKey` (subject+start), so reruns insert new / patch changed / delete removed, and **never touch events the user created manually**.

**Gotchas:**
- **Requires Legacy Outlook open.** New Outlook for Mac exposes **0 events** to AppleScript and **encrypts its tokens** at rest; OWA's REST API rejects cookie auth (401). So the browser/token/Graph routes were all dead — Legacy Outlook (AppleScript, local, no credentials) is the working path. If `get_outlook_events()` raises / returns nothing, Outlook is probably closed or in New Outlook mode (toggle off "New Outlook").
- **The "Day Job" calendar is a sync target — read-only.** Don't create/edit events on it manually (they'll be wiped/duplicated). Its id lives in `user.yaml` `calendars` with `label: Day Job`.
- Legacy Outlook is being retired by Microsoft over coming months; if events stop syncing, that's the likely cause.
- **⚠️ RECURRING EVENTS ARE CURRENTLY DROPPED (TODO, found 24 Jun 2026).** The AppleScript filters on the master event's `start time`, which for a recurring series is the *first* occurrence (often months in the past), so the whole series is excluded from the window. Net effect: **only one-off events sync; all daily huddles, weekly 1:1s, refinements etc. are missing.** Fix = detect `is recurring of e` and expand occurrences into the window (recurrence comes back as an AppleScript *record* — read its rule fields by label, project in Python). Until fixed, do NOT trust the synced Day Job calendar for recurring meetings — read Outlook directly. See `outlook.py` docstring.

## School newsletters: read the complete source before archiving

- Read the actual newsletter, not only the email wrapper or snippet. Inspect both HTML and plain text, attachments and linked documents; tracking links can hide a Google Docs URL in visible anchor text.
- Download the PDF, or export a linked Google Doc as PDF when accessible. Public Weduc PDF links need no portal login. Save the source locally in ignored activity records.
- Extract text and visually inspect image-only pages, posters, flyers and date tables. Empty extracted text does not mean an empty page.
- Use current child/year/class mappings from private user instructions. Recheck each school year. Include relevant class/year events, whole-school dates affecting the children and existing family tasks; exclude unrelated year groups and adverts.
- Check the configured family calendar before adding dates. Update changed details without duplicating repeated newsletter items. Use the configured family invitees, source links, child/class and preparation details. Use the configured time zone; do not invent times, deadlines or uncertain years.
- Optional club availability is not a booking. Add optional opportunities only when relevant to existing family plans, clearly marked not booked. Do not backfill expired adverts automatically.
- Track consent, payment, kit, costume, booking and childcare actions in existing Notion tasks where possible. Check receipts before treating generic payment reminders as unpaid debts. Optional donation requests do not authorize purchases.
- Summarize important relevant information and calendar changes concisely. Archive only after the full source is read, relevant calendar writes verified and actions tracked. If access fails, retain as pending and explain.
