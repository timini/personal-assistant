# pa-core — Package Instructions

## Goal
**Reliable shared infrastructure.** All plugins depend on this. Changes should be careful and minimal.

## Session start

Run `uv run pa-core memory brief` (or `uv run pa-core checkin` for a daily session) and get the date once with `uv run pa-core now` (or `get_now()` in Python). Do not rely on the harness's date, and do not call `get_now()` before every command.

## Key Components
- `config.py` — Loads `.env` and `user.yaml`. Exports `get_secret()`, `get_user_config()`, `PA_ROOT`, `get_now()`
- `cli_runner.py` — `run_cli()`, `parse_json_output()`, `run_gws()` for gws CLI calls
- `log.py` — `get_logger(name)` for consistent logging
- `setup.py` — Interactive first-run onboarding
- `daily_log.py` — Per-day JSON event logging in `activity/daily/`
  - `log_event(category, action, summary, details=None, project=None, links=None)` — append event (links: `{label: url}` dict for resource URLs). From the shell: `uv run pa-core log <category> <action> "<summary>" --details '<json>' --link label=url`
  - `get_today_events()` / `get_events(date)` — read events
  - Categories: `email`, `task`, `calendar`, `info`, `wellness`, `habit`, `other`
  - For structured metrics (wellness, habits, HR context). Narrative recall goes in the memory journal.
  - Session ID auto-generated per process
- `briefing.py` — Daily briefing generator from log + calendar + tasks
  - `generate_briefing(date=None)` → markdown string
  - `save_briefing(date=None)` → saves to `activity/briefings/YYYY-MM-DD.md`
  - Lazy imports pa-google and pa-notion; degrades gracefully if unavailable
- `flow_report.py` — Weekly opened/closed task aggregation + email-safe HTML
  - `aggregate_weeks(rows)` — buckets tasks into Monday-start weeks
  - Closed dates are **inferred** from last-edited time (Notion does not record status-change time), so recent closure counts can run high. The rendered report says so; don't present them as exact.
- `memory.py` — Shared assistant memory (see below)
- `prompts.py` — Deterministic morning and evening prompt text used by `checkin`
- `cli.py`: CLI entry point: `setup`, `checkin`, `context`, `briefing`, `memory`, `log`, `now`, `report`. `checkin` and `briefing` back up to Drive at most once a day (`last_backup` in `activity/.state.json`).
- `report.py`: research reports take JSON with `sections` holding `paragraphs`, `bullets`, `cards`, `table`, `calendar` and `sources`; see the `visual-report` skill. `--name` sets the output file names.

## Memory (`memory.py`)

Plain-file store at `private/memory/` (`$PA_MEMORY_DIR` or `memory_dir` in `user.yaml` override it):

- `entries/<name>.md`: one entry per file, YAML frontmatter (`name`, `type`, `summary`, `tags`, `due`, `source`, `status`, `created`, `updated`) and a Markdown body.
- `archive/<name>.md`: superseded entries and closed loops. Nothing is deleted.
- `journal/YYYY-MM.md`: dated one-line notes.

Types: `preference`, `lesson`, `person`, `fact`, `project`, `loop` (loops need a `due` date). Key functions: `add()` (upsert), `update()` (change some fields or append a dated note; `pa-core memory update`), `get()`, `list_entries()`, `search()`, `archive()`, `due_loops()`, `close_loop()`, `journal()`, `render_brief()`, `lint()`, `import_claude_memory()`. Tests isolate the store through `$PA_MEMORY_DIR` in the root `conftest.py`.

## Evening briefing

Collect the habit, gratitude and day-review answers in conversation and log them before running `pa-core briefing --evening`; otherwise the briefing reports everything as not logged.

## run_gws() Usage
```python
run_gws(service, resource, method, params=None, *, body=None, timeout=60, page_all=False)
```
- `resource` is dot or space separated — gets split into parts
- `params` → `--params '<json>'` flag
- `body` → `--json '<json>'` flag
- gws prints preamble before JSON; `parse_json_output()` skips non-JSON lines
