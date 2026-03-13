# pa-core — Package Instructions

## Goal
**Reliable shared infrastructure.** All plugins depend on this. Changes should be careful and minimal.

## Key Components
- `config.py` — Loads `.env` and `user.yaml`. Exports `get_secret()`, `get_user_config()`, `PA_ROOT`
- `cli_runner.py` — `run_cli()`, `parse_json_output()`, `run_gws()` for gws CLI calls
- `log.py` — `get_logger(name)` for consistent logging
- `setup.py` — Interactive first-run onboarding
- `daily_log.py` — Per-day JSON event logging in `activity/daily/`
  - `log_event(category, action, summary, details=None, project=None)` — append event
  - `get_today_events()` / `get_events(date)` — read events
  - Categories: `email`, `task`, `calendar`, `info`, `other`
  - Session ID auto-generated per process
- `briefing.py` — Daily briefing generator from log + calendar + tasks
  - `generate_briefing(date=None)` → markdown string
  - `save_briefing(date=None)` → saves to `activity/briefings/YYYY-MM-DD.md`
  - Lazy imports pa-google and pa-notion; degrades gracefully if unavailable
- `cli.py` — CLI entry point with subcommands: `setup`, `briefing`, `log`

## run_gws() Usage
```python
run_gws(service, resource, method, params=None, *, body=None, timeout=60, page_all=False)
```
- `resource` is dot or space separated — gets split into parts
- `params` → `--params '<json>'` flag
- `body` → `--json '<json>'` flag
- gws prints preamble before JSON; `parse_json_output()` skips non-JSON lines
