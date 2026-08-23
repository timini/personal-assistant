"""Email the weekly task-flow report.

    uv run python scripts/weekly_flow_email.py           # send it
    uv run python scripts/weekly_flow_email.py --dry-run # print the HTML, send nothing

Run weekly by a LaunchAgent (com.tim.weekly-flow-report). Deliberately does the
Notion query and the rendering in plain Python with no model in the loop — this
is deterministic collation, per ADR 0001.
"""
import base64
import sys
from email.message import EmailMessage

from pa_core.cli_runner import run_gws
from pa_core.config import get_secret, get_now, get_user_config
from pa_core.flow_report import aggregate_weeks, render_html
from pa_notion.client import NotionClient


def _status(props: dict) -> str:
    p = props.get("Status", {})
    return p["select"]["name"] if p.get("select") else ""


def fetch_rows() -> list[dict]:
    client = NotionClient()
    return [
        {
            "created": page.get("created_time", "")[:10],
            "edited": page.get("last_edited_time", "")[:10],
            "status": _status(page.get("properties", {})),
        }
        for page in client.query_database(get_secret("NOTION_TASKS_DB_ID"))
    ]


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    rows = fetch_rows()
    weeks = aggregate_weeks(rows)
    if not weeks:
        print("no task data, nothing to send")
        return

    totals = {
        "created": len(rows),
        "done": sum(1 for r in rows if r["status"] == "Done"),
        "discarded": sum(1 for r in rows if r["status"] == "Discarded"),
    }
    html = render_html(weeks, totals)

    if dry_run:
        print(html)
        return

    now = weeks[-1]
    direction = "down" if now["net"] < 0 else "up" if now["net"] > 0 else "level"
    msg = EmailMessage()
    recipient = get_user_config().get("email")
    if not recipient:
        raise SystemExit("No 'email' set in user.yaml — nowhere to send the report.")
    msg["To"] = recipient
    msg["Subject"] = (
        f"Task flow: {now['running']} open, {direction} "
        f"{abs(now['net'])} this week"
    )
    msg.set_content(
        f"Open now: {now['running']}. This week {now['opened']} opened, "
        f"{now['closed']} closed. Open this email in HTML for the charts."
    )
    msg.add_alternative(html, subtype="html")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = run_gws("gmail", "users.messages", "send", {"userId": "me"}, body={"raw": raw})
    print(f"sent {sent.get('id')} — {get_now()['display']}")


if __name__ == "__main__":
    main()
