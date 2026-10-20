"""Throughput / net-flow monitor — pure functions (no I/O, unit-testable).

Tracks tasks completed vs added so the list never silently builds back up.
Fed normalised task dicts + historical snapshot dicts; returns counts/strings.

Normalised task dict keys: id, title, status, lane, due (YYYY-MM-DD or ''),
created (YYYY-MM-DD or ISO), last_edited (ISO or YYYY-MM-DD).
"""

from collections import Counter
from datetime import date

AGING_DAYS = 10
LIVE = "🔥"


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _shift(today: str, days: int) -> str:
    return (_d(today) - __import__("datetime").timedelta(days=days)).isoformat()


def compute_snapshot(tasks: list[dict], today: str) -> dict:
    """Point-in-time counts from the current task set."""
    t = _d(today)
    open_tasks = [x for x in tasks if x.get("status") != "Done"]
    done_total = sum(1 for x in tasks if x.get("status") == "Done")

    aging_live = []
    for x in open_tasks:
        if (x.get("lane") or "").startswith(LIVE) and x.get("status") in ("To Do", "In Progress"):
            le = (x.get("last_edited") or "")[:10]
            stale = bool(le) and (t - _d(le)).days > AGING_DAYS
            overdue = bool(x.get("due")) and x["due"] < today
            if stale or overdue:
                aging_live.append(x["id"])

    return {
        "date": today,
        "open": len(open_tasks),
        "done_total": done_total,
        "by_lane": dict(Counter((x.get("lane") or "—") for x in open_tasks)),
        "by_status": dict(Counter((x.get("status") or "none") for x in open_tasks)),
        "added_today": sum(1 for x in tasks if (x.get("created") or "")[:10] == today),
        "overdue": sum(1 for x in open_tasks if x.get("due") and x["due"] < today),
        "live_open": sum(1 for x in open_tasks if (x.get("lane") or "").startswith(LIVE)),
        "aging_live": aging_live,
    }


def net_flow(snapshots: list[dict], tasks: list[dict], today: str, days: int = 7) -> dict:
    """Added vs completed over the rolling window. Prefers snapshot deltas for
    completions; falls back to Done last_edited_time before history exists."""
    win_start = _shift(today, days)
    current_open = sum(1 for x in tasks if x.get("status") != "Done")
    current_done = sum(1 for x in tasks if x.get("status") == "Done")

    added = sum(1 for x in tasks if x.get("created") and x["created"][:10] > win_start)

    snaps = sorted([s for s in snapshots], key=lambda s: s["date"])
    past = [s for s in snaps if s["date"] <= win_start]
    base = past[-1] if past else (snaps[0] if snaps else None)

    if base and "done_total" in base:
        completed = max(0, current_done - base["done_total"])
        source = "delta"
    else:
        completed = sum(
            1 for x in tasks
            if x.get("status") == "Done" and x.get("last_edited") and x["last_edited"][:10] > win_start
        )
        source = "last_edited"

    open_then = base["open"] if base and "open" in base else None
    open_trend = (current_open - open_then) if open_then is not None else None
    net = completed - added

    if net > 0 and (open_trend is None or open_trend <= 0):
        verdict = "clearing"
    elif net < 0 or (open_trend is not None and open_trend > 0):
        verdict = "building"
    else:
        verdict = "holding"

    return {
        "added": added, "completed": completed, "net": net,
        "open_now": current_open, "open_then": open_then, "open_trend": open_trend,
        "verdict": verdict, "source": source, "days": days,
    }


def flow_line(snapshot: dict, nf: dict) -> str:
    """One-line morning readout."""
    emoji = {"clearing": "✅", "holding": "➖", "building": "⚠️"}[nf["verdict"]]
    line = (f"📊 Flow ({nf['days']}d): +{nf['added']} added, {nf['completed']} done, "
            f"net {nf['net']:+d} — {nf['verdict']} {emoji}")
    if nf.get("open_then") is not None:
        line += f" · open {nf['open_then']}→{nf['open_now']}"
    extra = []
    if snapshot.get("overdue"):
        extra.append(f"{snapshot['overdue']} overdue")
    if snapshot.get("aging_live"):
        extra.append(f"{len(snapshot['aging_live'])} aging")
    if extra:
        line += " · ⚠️ " + ", ".join(extra)
    return line


def build_up_alerts(snapshots: list[dict], today: str) -> list[str]:
    """Proactive flags when work is backing up. Silent when on track.

    Expects snapshots ascending by date, each carrying verdict/overdue/aging_live.
    """
    snaps = sorted(snapshots, key=lambda s: s["date"])
    alerts: list[str] = []
    if not snaps:
        return alerts
    cur = snaps[-1]
    if len(snaps) >= 2:
        prev = snaps[-2]
        if cur.get("verdict") == "building" and prev.get("verdict") == "building":
            alerts.append("Net-flow has been BUILDING for 2+ days — you're adding faster than "
                          "closing. Suggest a clear-down session, park more, or pause adding to Live.")
        if cur.get("overdue", 0) > prev.get("overdue", 0):
            alerts.append(f"Overdue rising ({prev.get('overdue', 0)}→{cur.get('overdue', 0)}) — "
                          "let's knock out the overdue items before they pile up.")
    if cur.get("aging_live"):
        alerts.append(f"{len(cur['aging_live'])} Live task(s) aging/overdue — they're starting to "
                      "rot; let's action or re-scope them.")
    return alerts
