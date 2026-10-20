"""Daily task snapshot + net-flow readout.

Run each morning (part of the checkin routine). Writes an idempotent daily
snapshot to activity/snapshots/YYYY-MM-DD.json and prints the one-line flow
readout plus any build-up alerts.

    uv run python scripts/task_snapshot.py
    uv run python scripts/task_snapshot.py --json
"""
import json
import sys

from pa_core.config import PA_ROOT, get_secret, get_now
from pa_notion.client import NotionClient
from pa_notion import flow

SNAP_DIR = PA_ROOT / "activity" / "snapshots"


def _sel(props, name):
    p = props.get(name, {})
    return p["select"]["name"] if p.get("select") else ""


def _normalise(page: dict) -> dict:
    props = page.get("properties", {})
    tp = props.get("Task") or props.get("Name") or {}
    items = tp.get("title", [])
    due = props.get("Due Date", {}).get("date")
    return {
        "id": page["id"],
        "title": items[0]["plain_text"] if items else "",
        "status": _sel(props, "Status"),
        "lane": _sel(props, "Lane"),
        "due": (due.get("start", "") or "")[:10] if due else "",
        "created": page.get("created_time", ""),
        "last_edited": page.get("last_edited_time", ""),
    }


def _load_history(today: str) -> list[dict]:
    if not SNAP_DIR.exists():
        return []
    out = []
    for f in sorted(SNAP_DIR.glob("*.json")):
        if f.stem == today:
            continue  # today is recomputed fresh
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            pass
    return out


def main():
    as_json = "--json" in sys.argv
    today = get_now()["date"]

    client = NotionClient()
    pages = client.query_database(get_secret("NOTION_TASKS_DB_ID"))
    tasks = [_normalise(p) for p in pages]

    snap = flow.compute_snapshot(tasks, today)
    history = _load_history(today)
    nf = flow.net_flow(history, tasks, today, days=7)

    # stamp net/verdict onto the saved snapshot so alerts can read trend history
    snap["net7d"] = nf["net"]
    snap["verdict"] = nf["verdict"]

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    (SNAP_DIR / f"{today}.json").write_text(json.dumps(snap, indent=2))

    alerts = flow.build_up_alerts(history + [snap], today)

    if as_json:
        print(json.dumps({"snapshot": snap, "flow": nf, "alerts": alerts}, indent=2))
        return

    print(flow.flow_line(snap, nf))
    lanes = snap["by_lane"]
    print(f"   lanes: 🔥 {lanes.get('🔥 Live', 0)} live · "
          f"🅿️ {lanes.get('🅿️ Parked', 0)} parked · 💤 {lanes.get('💤 Someday', 0)} someday")
    for a in alerts:
        print(f"   ⚠️  {a}")


if __name__ == "__main__":
    main()
