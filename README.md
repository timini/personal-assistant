# PA — Personal Assistant CLI Toolkit

A modular personal assistant built as a Python uv workspace. Each integration is a standalone CLI tool that Claude Code, Codex, or another coding agent can invoke via `uv run <command>`. No MCP servers — just Python packages.

## Features

- **Notion** — Task management (list, add, update) via the Notion API
- **Google Workspace** — Email and calendar access via the `gws` CLI
- **Google Drive backup** — Automatic backup of personal/gitignored files to Drive
- **Daily briefing** — Generated daily summary from calendar, tasks, and event logs
- **Event logging** — Per-day JSON event log tracking actions across all integrations
- **Plugin architecture** — Add new integrations by dropping in a package
- **Activity logs** — Per-plugin event tracking so your AI assistant maintains context across sessions
- **No hardcoded config** — All user details come from `.env` and `user.yaml`, generated at setup

## Privacy: public toolkit, private user context

Treat every tracked file as public. Instructions must describe reusable behavior without identifying the user. Personal information belongs only in **ignored, untracked** files—even when it is not a password or secret.

| Location | Contents | Git |
|---|---|---|
| `AGENTS.md`, package instructions, skills, README | Generic workflows and technical guidance; synthetic examples | Tracked |
| `user-instructions.md` | Personal preferences, contacts, household rules and signatures | Ignored |
| `user.yaml`, `.env` | User configuration, resource IDs and credentials | Ignored |
| `private/` | Additional private context and historical instruction snapshots | Ignored |
| `activity/`, `output/`, `tmp/`, `download.*` | Logs, downloads and working artifacts | Ignored |
| `.codex/`, `.claude/settings.local.json`, `.claude/RESUME.md` | Local agent configuration and session notes | Ignored |

When asked to “remember” a personal fact or update personal instructions, write it to `user-instructions.md` or a referenced file under `private/`. Only put the reusable rule in public instructions. Do not include real names, employer details, addresses, contacts, family/class details, appointments, health readings, payment information or account IDs in examples, test fixtures, screenshots, filenames, commit messages or PR descriptions.

### Before committing or pushing

1. Confirm private destinations are ignored and untracked:
   ```bash
   git check-ignore -v user-instructions.md user.yaml .env private/health-preferences.md
   git ls-files -- user-instructions.md user.yaml .env private/ activity/ .codex/ .claude/settings.local.json .claude/RESUME.md
   ```
   The first command should show ignore rules; the second should produce no output.
2. Stage only explicitly reviewed files. Avoid `git add .`, `git add -A` and forced adds for personal-assistant work.
3. Inspect `git status --short`, `git diff --cached --name-only`, and the complete `git diff --cached`. Review prose and examples as carefully as credentials; a secret scanner cannot establish that a file is free of personal information. Run `git diff --cached --check`.
4. Publish only after the staged content is user-neutral. Keep private backups in an authorized private destination and review their contents and sharing.

Adding an ignore rule does **not** untrack existing files or erase earlier commits. If personal information was committed, sanitize the current tracked files and report the historical exposure. Removing it from repository history requires a separately coordinated history rewrite; do not silently force-push.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- For Google: [`gws` CLI](https://github.com/nicholasgasior/gws) installed and authenticated
- For Notion: A Notion integration with access to your workspace

### Setup

```bash
# Clone the repo
git clone <repo-url> && cd PA

# Install all packages
uv sync --all-packages

# Run interactive setup (generates .env and user.yaml)
uv run pa-core setup
```

Or configure manually:

1. Copy `.env.example` to `.env` and fill in your API tokens
2. Create `user.yaml` with your name, email, timezone, enabled plugins, and projects

### Usage

```bash
# Tasks (Notion)
uv run pa-notion tasks list
uv run pa-notion tasks list --status "To Do"
uv run pa-notion tasks add "Buy milk" --project "Shopping" --priority high
uv run pa-notion tasks update <task-id> --status "Done"

# Email & Calendar (Google Workspace)
uv run pa-google briefing              # Morning briefing: calendar + unread emails
uv run pa-google emails --unread --limit 5
uv run pa-google calendar              # Today's events
uv run pa-google calendar --days 7     # Next 7 days

# Backup personal files to Google Drive
uv run pa-google backup                # Upload tarball to PA-Backups folder
uv run pa-google backup --keep 10      # Keep 10 backups instead of default 7

# Daily briefing & event logging
uv run pa-core briefing                # Print today's daily briefing
uv run pa-core briefing --save         # Save briefing to activity/briefings/
uv run pa-core briefing --save --backup  # Save briefing + backup to Drive
uv run pa-core log email archived "Archived 5 newsletters"
uv run pa-core log task created "Created task: Pay bill" --project "Admin / Finance"
```

Most list commands support `--json` for machine-readable output.

## Project Structure

```
PA/
├── packages/
│   ├── pa-core/        # Shared: config, CLI runner, logging, setup
│   ├── pa-google/      # Google Workspace (wraps gws CLI)
│   ├── pa-notion/      # Notion API client + task management
│   ├── pa-whatsapp/    # WhatsApp (stub — future)
│   └── pa-finance/     # Finance / open banking (stub — future)
├── scripts/            # Standalone scripts (daily briefing, weekly review)
├── activity/           # Per-user activity logs (gitignored)
├── .env.example        # Template for required environment variables
├── user.yaml           # User config — generated at setup (gitignored)
└── pyproject.toml      # uv workspace root
```

## Adding a Plugin

1. Create `packages/pa-<name>/` with a `pyproject.toml` depending on `pa-core`
2. Implement `client.py` (core logic) and `cli.py` (entry point)
3. Register the CLI in `[project.scripts]`
4. Create `activity/log.md` for the plugin
5. Run `uv sync`

See existing packages for the pattern.

## Configuration

### `.env` (secrets — gitignored)

See [`.env.example`](.env.example) for all supported keys.

### `user.yaml` (user config — gitignored)

```yaml
name: Your Name
email: you@example.com
timezone: Europe/London
enabled_plugins:
  - pa-google
  - pa-notion
projects:
  - name: My Project
    category: work
```

## How It Works with AI Assistants

This toolkit supports both Claude Code and Codex. The assistant calls CLI commands via the shell, reads their output, and uses the activity logs to maintain context across sessions. `AGENTS.md` is the canonical handbook; `CLAUDE.md` imports it for backward compatibility. Package-specific guidance follows the same `AGENTS.md` plus `CLAUDE.md` wrapper pattern.

Local agent settings belong in ignored `.codex/` or `.claude/settings.local.json`. Select permissions appropriate to your environment; repository documentation does not override runtime permissions or user authorization.

## License

MIT
