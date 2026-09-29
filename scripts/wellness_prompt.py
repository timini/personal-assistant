"""Send the morning planning prompt or the evening reflection prompt.

    uv run python scripts/wellness_prompt.py --morning
    uv run python scripts/wellness_prompt.py --evening --dry-run

Driven by LaunchAgents whose times come from `checkins:` in user.yaml — see
`pa-core schedule-checkins`. Deterministic: no model in the loop, per ADR 0001.

Every failure path Telegrams rather than dying silently. Two scheduled jobs
failed invisibly on 2026-08-24 (a wrong uv path, then a wrong git branch),
producing no output and empty logs. Silence is the failure mode that matters.
"""
import argparse
import sys
import traceback

from pa_core.config import get_now, get_user_config
from pa_core.prompts import build_evening_prompt, build_morning_prompt


def _safe(fn, default):
    """Never let one dead source stop the prompt going out."""
    try:
        return fn()
    except Exception:
        return default


def morning_text() -> str:
    from pa_core.context import _fetch_calendar, _fetch_health
    today = get_now()["date"]
    return build_morning_prompt(
        schedule=_safe(_fetch_calendar, []),
        tasks=_safe(_open_tasks, []),
        today=today,
        health=_safe(lambda: _fetch_health(today), None),
    )


def evening_text() -> str:
    from pa_core.daily_log import get_events
    today = get_now()["date"]
    config = get_user_config()
    return build_evening_prompt(
        habits=config.get("habits", []),
        events=_safe(lambda: get_events(today), []),
        today=today,
        tomorrow_tasks=_safe(_open_tasks, [])[:3],
    )


def _open_tasks() -> list[dict]:
    from pa_notion.tasks import list_tasks
    return [t for t in list_tasks() if t.get("status") not in ("Done", "Discarded")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a wellness/planning prompt")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--morning", action="store_true")
    group.add_argument("--evening", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print it, send nothing")
    args = parser.parse_args()

    which = "morning" if args.morning else "evening"
    try:
        text = morning_text() if args.morning else evening_text()
    except Exception:
        _alert(f"{which} prompt failed to build", traceback.format_exc())
        raise

    if args.dry_run:
        print(text)
        return

    try:
        from pa_telegram.client import send_message
        send_message(text, parse_mode="")
        print(f"{which} prompt sent — {get_now()['display']}")
    except Exception:
        _alert(f"{which} prompt failed to send", traceback.format_exc())
        raise


def _alert(summary: str, detail: str) -> None:
    """Shout about a failure. Best effort — never raises."""
    try:
        from pa_telegram.client import send_message
        send_message(f"⚠️ {summary}\n\n{detail[-600:]}", parse_mode="")
    except Exception:
        print(f"{summary}\n{detail}", file=sys.stderr)


if __name__ == "__main__":
    main()
