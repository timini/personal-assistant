# Personal Assistant (PA) Project

## Overview

A personal assistant CLI toolkit built as a Python uv workspace monorepo. Each integration is a separate package with a CLI entry point. Claude uses them via `uv run <command>`. No MCP servers.

All user-specific config comes from `.env` (secrets) and `user.yaml` (non-secret config). Both are gitignored. No hardcoded user details in code.

## IMPORTANT: Read Instruction Files

Before doing any work, read the relevant instruction files. These contain critical rules and gotchas.

**User-specific instructions (gitignored — personal workflows, contacts, calendar rules):**
- `user-instructions.md` — MUST READ for email handling, calendar events, family info, contacts

**Per-package instructions (committed — how each package works):**
- `packages/pa-core/INSTRUCTIONS.md` — Shared infrastructure rules
- `packages/pa-google/INSTRUCTIONS.md` — Email triage, Gmail gotchas, Drive workflow
- `packages/pa-notion/INSTRUCTIONS.md` — Task rules, DB schema, sub-task pattern
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

# Google Workspace
uv run pa-google briefing                      # Morning briefing (calendar + inbox emails)
uv run pa-google emails                        # All inbox emails (default: all, not just unread)
uv run pa-google emails --unread               # Only unread inbox emails
uv run pa-google calendar                      # Today's events
uv run pa-google calendar --days 7             # Next 7 days
uv run pa-google backup                        # Backup personal files to Google Drive
uv run pa-google backup --keep 10              # Keep 10 backups instead of default 7

# Daily briefing & event logging
uv run pa-core briefing                        # Print today's daily briefing
uv run pa-core briefing --save                 # Save briefing to activity/briefings/
uv run pa-core briefing --save --backup        # Save briefing + backup personal files to Drive
uv run pa-core briefing --date 2026-03-12      # Briefing for a specific date
uv run pa-core log email archived "Archived 5 newsletters"
uv run pa-core log task created "Created task: Pay credit card" --project "Admin / Finance"

# Setup
uv run pa-core setup                           # Interactive first-run onboarding

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
- `calendar.py` — `get_todays_events()`, `get_upcoming_events()`
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
enabled_plugins:
  - pa-google
  - pa-notion
projects:
  - name: Project Name
    category: work|personal
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
```

- **Categories**: `email`, `task`, `calendar`, `info`, `other`
- **Actions**: freeform but conventional — `archived`, `created`, `completed`, `surfaced`, `flagged`
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

### Daily
1. Run email triage (above)
2. Check calendar with `pa-google calendar` for today's context
3. Review open tasks with `pa-notion tasks list --status "To Do"` and suggest priorities
4. Save briefing with backup: `pa-core briefing --save --backup`

### Weekly
1. Full task review — check for stale, overdue, or completed tasks
2. Prep for upcoming meetings/1:1s using calendar
3. Update activity logs with significant events
