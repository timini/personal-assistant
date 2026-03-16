# Personal Assistant (PA) Project

## Overview

A personal assistant CLI toolkit built as a Python uv workspace monorepo. Each integration is a separate package with a CLI entry point. Claude uses them via `uv run <command>`. No MCP servers.

All user-specific config comes from `.env` (secrets) and `user.yaml` (non-secret config). Both are gitignored. No hardcoded user details in code.

## IMPORTANT: Check Date/Time FIRST

**At the very start of every session**, call `get_now()` to get the actual current date, day, and time. Never rely on system-provided date context or assumptions.

```python
from pa_core.config import get_now
now = get_now()  # → {"date": "2026-03-16", "day": "Monday", "time": "09:13", "period": "morning", ...}
```

Use this to determine morning vs evening checkin, fetch the right calendar day, and check upcoming due dates.

## IMPORTANT: Read Instruction Files

Before doing any work, read the relevant instruction files. These contain critical rules and gotchas.

**User-specific instructions (gitignored — personal workflows, contacts, calendar rules):**
- `user-instructions.md` — MUST READ for email handling, calendar events, family info, contacts

**Per-package instructions (committed — how each package works):**
- `packages/pa-core/INSTRUCTIONS.md` — Shared infrastructure rules
- `packages/pa-google/INSTRUCTIONS.md` — Email triage, Gmail gotchas, Drive workflow
- `packages/pa-notion/INSTRUCTIONS.md` — Task rules, DB schema, sub-task pattern
- `packages/pa-telegram/INSTRUCTIONS.md` — Telegram setup, message formatting
- `packages/pa-whatsapp/INSTRUCTIONS.md` — Status and goals
- `packages/pa-finance/INSTRUCTIONS.md` — Status and goals

## Quick Reference — CLI Commands

```bash
# Notion tasks
uv run pa-notion tasks list                    # List all tasks
uv run pa-notion tasks list --status "To Do"   # Filter by status
uv run pa-notion tasks list --json             # JSON output
uv run pa-notion tasks add "Buy milk" --project "Shopping" --priority high --notes "context here"
uv run pa-notion tasks update <id> --status "Done"
uv run pa-notion tasks promote <id>                # Promote to Google Tasks "Today" list
uv run pa-notion tasks promote <id> --due 2026-03-14  # With explicit due date
uv run pa-notion tasks sync                    # Sync completed Google Tasks → Notion (auto-runs during briefings)

# Google Workspace
uv run pa-google briefing                      # Morning briefing (calendar + inbox emails)
uv run pa-google emails                        # All inbox emails (default: all, not just unread)
uv run pa-google emails --unread               # Only unread inbox emails
uv run pa-google calendar                      # Today's events (all configured calendars)
uv run pa-google calendar --days 7             # Next 7 days (all configured calendars)
uv run pa-google calendar --json               # JSON output with "calendar" field per event
uv run pa-google calendar-check                # Verify all configured calendars are accessible
uv run pa-google backup                        # Backup personal files to Google Drive
uv run pa-google backup --keep 10              # Keep 10 backups instead of default 7

# Daily check-in (single entry point — does everything)
uv run pa-core checkin                         # Sync tasks + backup + full context + coaching prompt
uv run pa-core checkin --evening               # Evening session (habits, gratitude, tomorrow preview)
uv run pa-core checkin --no-backup             # Skip Google Drive backup
uv run pa-core checkin --json                  # JSON context output (no coaching prompt)

# Session context (context only, no sync/backup)
uv run pa-core context                         # Today's full context (calendar + emails + tasks + habits + weather)
uv run pa-core context --json                  # JSON output

# Daily briefing & event logging
uv run pa-core briefing                        # Print today's daily briefing
uv run pa-core briefing --save                 # Save briefing to activity/briefings/
uv run pa-core briefing --save --backup        # Save briefing + backup personal files to Drive
uv run pa-core briefing --save --backup --telegram  # Save + backup + send to Telegram
uv run pa-core briefing --date 2026-03-12      # Briefing for a specific date
uv run pa-core briefing --evening              # Evening briefing (wins, habits, tomorrow focus)
uv run pa-core briefing --evening --save       # Save evening briefing to activity/briefings/
uv run pa-core briefing --evening --save --telegram  # Save + send evening briefing to Telegram
uv run pa-core log email archived "Archived 5 newsletters"
uv run pa-core log task created "Created task: Pay credit card" --project "Admin / Finance"

# Setup
uv run pa-core setup                           # Interactive first-run onboarding

# Telegram notifications
uv run pa-telegram send "Hello world"          # Send arbitrary message
uv run pa-telegram briefing                     # Send today's briefing to Telegram
uv run pa-telegram briefing --evening           # Send evening briefing to Telegram
uv run pa-telegram briefing --date 2026-03-12   # Send specific date's briefing

# Stubs (not yet implemented)
uv run pa-whatsapp
uv run pa-finance
```

## Project Structure

```
PA/
├── CLAUDE.md                    # This file — project docs
├── .env                         # Secrets (gitignored)
├── .env.example                 # Template for .env
├── user.yaml                    # User config (gitignored)
├── pyproject.toml               # uv workspace root
├── uv.lock
├── activity/
│   ├── log.md                   # Root activity log
│   ├── daily/                   # Per-day event logs (JSON, gitignored)
│   └── briefings/               # Generated briefings (markdown, gitignored)
├── packages/
│   ├── pa-core/                 # Shared: config, CLI runner, logging, setup
│   ├── pa-google/               # Google Workspace (wraps gws CLI)
│   ├── pa-notion/               # Notion (httpx API client)
│   ├── pa-telegram/             # Telegram (notifications & briefings)
│   ├── pa-whatsapp/             # WhatsApp (stub)
│   └── pa-finance/              # Finance/Lunchflow (stub)
└── scripts/
    ├── daily-briefing.py
    └── weekly-review.py
```

## Package Goals & Details

Each package has a clear goal that drives how Claude should use it.

### pa-core
**Goal: Reliable shared infrastructure that all plugins depend on.**
Shared utilities — NO integration-specific code. If core is broken, everything is broken, so changes here should be careful and minimal.
- `config.py` — Loads `.env` and `user.yaml`. Exports `get_secret()`, `get_user_config()`, `PA_ROOT`.
- `cli_runner.py` — `run_cli()` subprocess wrapper, `parse_json_output()`, `run_gws()` convenience for gws CLI.
- `log.py` — `get_logger(name)` for consistent logging.
- `setup.py` — Interactive first-run: generates `user.yaml`, guides integration setup.
- `daily_log.py` — `log_event()`, `get_today_events()` — per-day JSON event log in `activity/daily/`.
- `briefing.py` — `generate_briefing()`, `save_briefing()` — daily briefing from log + calendar + tasks.
- `cli.py` — CLI entry point: `setup`, `briefing`, `log` subcommands.

### pa-google
**Goal: Inbox Zero.** The inbox should be empty at all times. When processing emails, Claude should immediately take action on every message — archive noise, reply where possible, snooze time-sensitive items, or create a Notion task for anything that needs follow-up later. No email should sit unread in the inbox without a decision being made. Calendar awareness supports this by providing context for scheduling and priorities.
- `gmail.py` — `get_inbox_emails()`, `archive_email()`, `get_email_body()`
- `calendar.py` — Multi-calendar support: `get_all_todays_events()`, `get_all_upcoming_events()`, `check_calendars()`. Reads `calendars` list from `user.yaml` (falls back to primary-only). Each event dict includes a `"calendar"` field with the label.
- `cli.py` — CLI entry point with `briefing`, `emails`, `calendar` commands

### pa-notion
**Goal: Single source of truth for all tasks and commitments.** Every actionable item — from emails, conversations, or ad-hoc requests — should end up as a Notion task with the right project, priority, and status. Claude should keep this list current: close completed tasks, escalate overdue ones, and ensure nothing falls through the cracks.
- `client.py` — `NotionClient` class: query, create, update pages
- `tasks.py` — `list_tasks()`, `add_task()`, `update_task()` against NOTION_TASKS_DB_ID
- `cli.py` — CLI entry point with `tasks list|add|update` commands

**Notion DB schema** (Tasks database):
- `Task` (title), `Status` (select: To Do/In Progress/Waiting/Done), `Priority` (select: Urgent/High/Medium/Low)
- `Project` (select: Day Job, AI Transformation, Line Management, House Renovation, House Declutter, Garden, Fitness, Music, Landplan, Admin / Finance)
- `Due Date` (date), `Notes` (rich_text — use for email links etc), `Parent Task` (self-relation — for sub-tasks)

**Sub-task pattern**: Create a parent task, then link children via `Parent Task` relation:
```python
parent_id = client.create_page(db_id, parent_props)["id"]
client.update_page(child_id, {"Parent Task": {"relation": [{"id": parent_id}]}})
```

### pa-telegram
**Goal: Deliver briefings and notifications to Tim's phone.** Outbound-only — sends daily briefings and ad-hoc messages via Telegram Bot API. Uses plain `httpx` against `api.telegram.org`, no heavy dependencies.
- `client.py` — `send_message()`, `send_briefing()`, `_format_for_telegram()`
- `cli.py` — CLI entry point with `send` and `briefing` subcommands

### pa-whatsapp (stub)
**Goal: Surface and act on important messages.** WhatsApp is a high-noise channel. The goal is to flag messages that need a response or action, and ignore the rest. Not yet implemented — needs WhatsApp API research.

### pa-finance (stub)
**Goal: Financial awareness and bill tracking.** Surface upcoming payments, flag overdue bills, and provide spending summaries so nothing gets missed. Not yet implemented — needs Lunchflow setup.

## Configuration

### .env (secrets)
Contains API tokens and credentials. See `.env.example` for required keys.

### user.yaml (non-secret config)
```yaml
name: User Name
email: user@example.com
timezone: Europe/London
assistant_name: PA                               # Optional — display name used in briefing headers, defaults to "PA"
enabled_plugins:
  - pa-google
  - pa-notion
  - pa-telegram
projects:
  - name: Project Name
    category: work|personal
calendars:                                       # Optional — falls back to primary-only
  - id: "primary"
    label: null                                  # No label for primary calendar
  - id: "<calendar-id>@group.calendar.google.com"
    label: "Work"                                # Label shown in briefings as [Work]
```

Generated by `uv run pa-core setup` or manually created.

## Activity Log System

Each package has `activity/log.md` tracking events, decisions, and state for that integration. The root `activity/log.md` links them all and tracks cross-cutting events.

When Claude does significant work with a plugin, it should update that plugin's activity log with what happened.

## Adding a New Plugin

1. Create `packages/pa-<name>/` with `pyproject.toml`, `src/pa_<name>/`, `activity/log.md`
2. Add `pa-core` as workspace dependency with `[tool.uv.sources] pa-core = { workspace = true }`
3. Register CLI in `[project.scripts]`: `pa-<name> = "pa_<name>.cli:main"`
4. Implement: `client.py` (core logic), `cli.py` (CLI entry point)
5. Add link in root `activity/log.md`
6. Document in this file
7. Run `uv sync`

## Important: Gmail Gotchas

### Archive by THREAD, not message
Gmail's UI displays threads. When archiving, ALWAYS use `gws gmail users threads modify` — NOT `messages modify`. Archiving individual messages does NOT remove the thread from the inbox if other messages in the thread still exist. Use the `archive_email()` helper in `pa_google.gmail` which handles this correctly.

```bash
# WRONG — thread stays in inbox:
gws gmail users messages modify --params '{"userId":"me","id":"<msg_id>"}' --json '{"removeLabelIds":["INBOX"]}'

# RIGHT — archives the whole thread:
gws gmail users threads modify --params '{"userId":"me","id":"<thread_id>"}' --json '{"removeLabelIds":["INBOX","UNREAD"]}'
```

### gws CLI syntax
- Resources are space-separated: `users messages` not `users.messages`
- Parameters go in `--params '<json>'`, request body in `--json '<json>'`
- gws prints info lines to stdout before JSON — `parse_json_output()` in cli_runner handles this by skipping non-JSON preamble

## Daily Event Logging

Claude should log significant actions using `pa_core.daily_log.log_event()` during sessions. This builds up a record of what happened each day, which feeds into the daily briefing.

```python
from pa_core.daily_log import log_event

log_event("email", "archived", "Archived 5 newsletters")
log_event("task", "created", "Created task: Pay credit card bill", project="Admin / Finance")
log_event("calendar", "created", "Created 5 school events on Family Calendar")
log_event("info", "surfaced", "Summer club booking opens Wed 18 Mar at midday")
log_event("habit", "completed", "Exercise", details={"type": "configured", "duration_min": 30, "note": "Morning run"})
log_event("habit", "skipped", "Meditation", details={"type": "configured", "reason": "no time"})
log_event("calendar", "created", "Sprint Planning", links={"event": "https://calendar.google.com/..."})
log_event("email", "drafted", "Lusso complaint", links={"draft": "https://mail.google.com/mail/u/0/#drafts/..."})
log_event("task", "created", "Pay invoice", project="Admin / Finance", links={"task": "https://notion.so/..."})
```

- **Categories**: `email`, `task`, `calendar`, `info`, `wellness`, `habit`, `other`
- **Actions**: freeform but conventional — `archived`, `created`, `completed`, `surfaced`, `flagged`
- **Links**: optional `links={label: url}` dict — resource URLs are stored in the event and rendered in briefings
- **Storage**: `activity/daily/YYYY-MM-DD.json` (gitignored)
- **Session ID**: auto-generated per process, groups events by Claude session

At end of session or on request: `uv run pa-core briefing`

## Suggested Workflows

### Email triage (Inbox Zero)
1. Fetch ALL inbox emails with `uv run pa-google emails` (gets read + unread, not just unread)
2. For each email, decide immediately:
   - **Noise** (newsletters, notifications, delivery updates) → archive
   - **Quick action** (pay a bill, RSVP, short reply) → do it now, then archive
   - **Needs follow-up** → create a Notion task with context, then archive
   - **Time-sensitive** → flag to user, or snooze if possible
3. **If an email already has a matching Notion task, or you create one, always archive the email immediately.** Don't keep emails in the inbox as reminders — that's what Notion tasks are for.
4. **When creating or updating a Notion task from an email, include a link to the email** in the task notes. Gmail links: `https://mail.google.com/mail/u/0/#inbox/<message_id>`
5. Goal: inbox should be empty after every triage session

### Email attachments → Google Drive
When processing emails with attachments (non-spam):
1. **Save all attachments to Google Drive** using `gws drive` CLI
2. **Organise into project folders** — e.g. `PA/Garden/Designer - Garden Design/`, `PA/House Renovation/Builder Co/`
3. **Link the Drive files** in the relevant Notion project page and/or task notes
4. Drive folder structure should mirror the project structure in Notion
5. Use `gws gmail users messages attachments get` to download, then `gws drive files create` to upload

```bash
# Get attachment from email
gws gmail users messages attachments get --params '{"userId":"me","messageId":"<msg_id>","id":"<attachment_id>"}'

# Upload to Drive folder
gws drive files create --params '{"name":"<filename>","parents":["<folder_id>"]}' --upload <local_path>
```

### Task organisation
When organising tasks:
- **Group related tasks** under a parent using the `Parent Task` relation (sub-tasks)
- **Clear task names** — include enough context to act on (e.g. "Pay invoice for project X" not "invoice X")
- **Set due dates** on time-sensitive items — work backwards from actual deadlines
- **Every task needs**: status, priority, project, and clear title
- **Present tasks grouped by project** and sorted by priority/due date

### Google Tasks — Daily Active Tasks
**Google Tasks is where Tim looks for his daily to-do list.** Notion is the master database for all tasks, but daily/actionable tasks MUST also be added to Google Tasks so they show up on Tim's phone and widgets.

**Task lists:**
- `🌈Today` (ID: `MTEzODI3MTczMzYzODUyNzM2NDM6MDow`) — today's actionable tasks

**Rules:**
- **Notion is ALWAYS the source of truth.** Every task MUST exist in Notion first. Google Tasks is a secondary view.
- When creating a task: create in Notion FIRST → then add to Google Tasks with a link back to the Notion page
- **Every Google Task MUST include a Notion link** in the `notes` field so Tim can tap through to the full task
- Set `due` date on Google Tasks entries
- When a task is completed in Notion, also mark it done in Google Tasks (or vice versa)
- Google Tasks is the "active view" — Notion is the "full database"
- **Auto-sync**: `sync_google_tasks()` runs automatically at the start of every briefing (morning + evening), syncing completed Google Tasks back to Notion and cleaning up the completed entries. Can also be run manually via `uv run pa-notion tasks sync`.

**Notion page URL format:** `https://www.notion.so/<page_id_with_dashes_removed>`

```bash
# Add a task to Today list (ALWAYS include Notion link in notes)
gws tasks tasks insert --params '{"tasklist": "MTEzODI3MTczMzYzODUyNzM2NDM6MDow"}' --json '{"title": "Task name", "due": "2026-03-14T00:00:00Z", "notes": "https://www.notion.so/<notion_page_id>"}'

# List tasks in Today
gws tasks tasks list --params '{"tasklist": "MTEzODI3MTczMzYzODUyNzM2NDM6MDow"}'

# Complete a task
gws tasks tasks patch --params '{"tasklist": "MTEzODI3MTczMzYzODUyNzM2NDM6MDow", "task": "<task_id>"}' --json '{"status": "completed"}'
```

### Daily
1. **Run `uv run pa-core checkin`** — syncs Google Tasks, backs up to Drive, fetches full context
2. Follow the coaching prompt output: wellness check-in, then present tasks matched to energy
3. Run email triage (above)
4. At end of session: `uv run pa-core briefing --save --telegram`

### Evening
1. **Run `uv run pa-core checkin --evening`** — syncs tasks, backs up, fetches context
2. Follow the coaching prompt: habit check-in, freeform wins, gratitude, tomorrow preview
3. Generate and save evening briefing: `uv run pa-core briefing --evening --save --telegram`

### Weekly
1. Full task review — check for stale, overdue, or completed tasks
2. Prep for upcoming meetings/1:1s using calendar
3. Update activity logs with significant events

## Interaction Style — Wellness-Aware Sessions

### Session Opening — Always Check In First
Start every session by asking Tim how he's doing. Use multiple choice:

"How are you doing?
1. Great — firing on all cylinders
2. Good — solid, ready to go
3. Okay — managing
4. Rough — low energy or stressed
5. Bad — struggling today

And physically?
A. Well rested, feeling strong
B. Tired but functional
C. Run down / unwell
D. Something specific (ask)"

Log the response: `log_event("wellness", "check_in", "Morning check-in", details={...})`

### Task Presentation — Never Overwhelm
- NEVER dump full task lists. Maximum 5 tasks at a time, always curated.
- Match load to energy:
  - High energy → 3-5 tasks including harder items
  - Medium energy → 2-3 tasks, mix of easy wins + one important
  - Low/depleted → 1-2 easy wins only
- Frame positively: "Here's what would make today a win" not "Here's what's overdue"
- After completing a task, celebrate briefly, then offer the next one
- Use multiple choice where possible: "Which of these 3 feels most doable right now?"

### Periodic Check-Ins
- After 3-4 tasks or ~45 mins, check energy: "Still [X] or has it shifted? (1-5 or just a word)"
- If energy drops, scale back immediately
- If depleted, suggest a break and offer to wrap up

### Burnout Prevention
- At session start, silently review last 7 days of wellness logs
- If 3+ days of low/depleted energy or rough/bad mood:
  - Acknowledge gently: "Noticed energy has been low this week"
  - Reduce to absolute essentials only
  - Suggest one small win for morale
  - Do NOT pile on overdue items
- Track weekly patterns (Monday blues, Friday fatigue, etc.)

### Adaptive Coaching — Push or Protect
The coaching style should adapt based on all available signals (check-in, calendar density, health watch data when available, recent wellness trend):

**When Tim is strong** (high energy, light calendar, good sleep):
- Push him: "You've got capacity today — let's knock out something big"
- Suggest harder/important tasks, not just easy wins
- Set ambitious but realistic goals for the day
- Challenge him: "You could close 5 tasks today if you stay focused"

**When Tim is struggling** (low energy, rough mood, bad sleep, packed calendar):
- Protect him: "Tough day ahead — let's keep it light and get through it"
- Suggest only 1-2 easy wins
- Proactively defer non-urgent tasks
- Example: "I see you didn't sleep well and you've got back-to-back meetings. Let's just handle the one urgent thing and call it a win."

**Reading the room:** Combine all signals — don't rely on just one. Bad sleep + light calendar = still manageable. Good mood + packed calendar = focus on meetings, defer tasks. Multiple bad signals = full protection mode.

### Motivational Tone
- Warm but professional — Tim is an engineer, not a patient
- Celebrate concretely: "3 tasks done, solid morning" not generic cheerleading
- Frame days as winnable: "3 things would make today a win..."
- When overwhelmed: "Let's just pick one thing. What feels most doable?"

### Evening Session — Reflect and Wind Down
When running an evening session or evening briefing:

1. **Habit check-in** — Go through configured habits from user.yaml:
   "Let's check in on today's habits:
   1. Exercise — did you get any in today?
   2. Reading — any pages?
   3. Meditation — even 5 minutes?
   (Plus anything else you want to log)"

   Log each as: `log_event("habit", "completed"|"skipped", habit_name, details={...})`

2. **Gratitude** — Ask: "What's one thing you're grateful for today?"
   Log as: `log_event("wellness", "gratitude", "answer text")`

3. **Tomorrow preview** — Show auto-suggested top 3 tasks, ask:
   "Here's what I'd suggest for tomorrow — does this look right, or would you swap anything?"

4. **Wrap up** — Generate and send evening briefing:
   `uv run pa-core briefing --evening --save --telegram`

### Health Watch Data (Future Extension)
When a health watch module is added later, it will provide sleep duration/quality, resting heart rate, activity levels, etc. The briefing's "How You're Doing" section should incorporate this data alongside the self-reported check-in. The coaching logic should treat watch data as another signal — e.g., poor sleep data should trigger gentler coaching even if Tim says he feels "okay".
