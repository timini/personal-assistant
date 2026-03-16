# pa-core — Package Instructions

## Goal
**Reliable shared infrastructure.** All plugins depend on this. Changes should be careful and minimal.

## Session Start — MANDATORY

**ALWAYS call `get_now()` at the very start of every session.** Do NOT rely on system-provided dates or assumptions about what day it is. This returns the actual local date, day of week, time, and period (morning/afternoon/evening).

```python
from pa_core.config import get_now
now = get_now()  # Returns: date, day, time, timezone, period, display
```

Use this to:
- Determine morning vs evening checkin (`now["period"]`)
- Fetch the correct day's calendar events (`now["date"]`)
- Check for tasks with upcoming due dates relative to the actual date
- Display the correct day/date in briefings and greetings

**Never assume the date from context or conversation metadata — always call `get_now()`.**

## Key Components
- `config.py` — Loads `.env` and `user.yaml`. Exports `get_secret()`, `get_user_config()`, `PA_ROOT`, `get_now()`
- `cli_runner.py` — `run_cli()`, `parse_json_output()`, `run_gws()` for gws CLI calls
- `log.py` — `get_logger(name)` for consistent logging
- `setup.py` — Interactive first-run onboarding
- `daily_log.py` — Per-day JSON event logging in `activity/daily/`
  - `log_event(category, action, summary, details=None, project=None, links=None)` — append event (links: `{label: url}` dict for resource URLs)
  - `get_today_events()` / `get_events(date)` — read events
  - Categories: `email`, `task`, `calendar`, `info`, `other`
  - Session ID auto-generated per process
- `briefing.py` — Daily briefing generator from log + calendar + tasks
  - `generate_briefing(date=None)` → markdown string
  - `save_briefing(date=None)` → saves to `activity/briefings/YYYY-MM-DD.md`
  - Lazy imports pa-google and pa-notion; degrades gracefully if unavailable
- `cli.py` — CLI entry point with subcommands: `setup`, `briefing`, `log`

## Evening Briefing — Important

**The evening briefing MUST include an interactive check-in BEFORE generating the briefing.** Do NOT just run `pa-core briefing --evening` without first collecting habit and gratitude data — otherwise the briefing will say "not logged" for everything.

Flow: Send check-in questions via Telegram → wait for replies → log events → THEN generate briefing. See `pa-telegram/INSTRUCTIONS.md` for the full interim flow.

## run_gws() Usage
```python
run_gws(service, resource, method, params=None, *, body=None, timeout=60, page_all=False)
```
- `resource` is dot or space separated — gets split into parts
- `params` → `--params '<json>'` flag
- `body` → `--json '<json>'` flag
- gws prints preamble before JSON; `parse_json_output()` skips non-JSON lines
