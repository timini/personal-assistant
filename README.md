# PA — Personal Assistant CLI Toolkit

A modular personal assistant built as a Python uv workspace. Each integration is a standalone CLI tool that Claude (or any AI assistant) can invoke via `uv run <command>`. No MCP servers — just Python packages.

## Features

- **Notion** — Task management (list, add, update) via the Notion API
- **Google Workspace** — Email and calendar access via the `gws` CLI
- **Google Drive backup** — Automatic backup of personal/gitignored files to Drive
- **Daily briefing** — Generated daily summary from calendar, tasks, and event logs
- **Event logging** — Per-day JSON event log tracking actions across all integrations
- **Plugin architecture** — Add new integrations by dropping in a package
- **Activity logs** — Per-plugin event tracking so your AI assistant maintains context across sessions
- **No hardcoded config** — All user details come from `.env` and `user.yaml`, generated at setup

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

This toolkit is designed to be used by Claude Code (or similar AI coding assistants). The assistant calls CLI commands via bash, reads the output, and uses the activity logs to maintain context across sessions. The `CLAUDE.md` file documents all available commands and workflows.

## License

MIT
