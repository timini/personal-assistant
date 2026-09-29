"""Weekly task-flow aggregation and report rendering.

Opened is exact — it comes from each task's creation timestamp. Closed is
*inferred* from the last-edited timestamp of tasks now marked Done or
Discarded, because Notion does not record when a status last changed. A closed
task edited later (adding notes, say) lands in the week of that edit rather
than the week it was really closed. The rendered report states this; do not
present the closed figures as exact.
"""
from __future__ import annotations

import datetime

CLOSED_STATUSES = ("Done", "Discarded")


def week_start(date_str: str) -> str:
    """ISO date of the Monday of the week containing date_str."""
    d = datetime.date.fromisoformat(date_str[:10])
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def aggregate_weeks(rows: list[dict]) -> list[dict]:
    """Bucket tasks into weeks. Each row needs created, edited and status.

    Rows missing a timestamp are skipped for that side of the ledger rather
    than dropped entirely — a task with no created date can still be counted
    as closed, and vice versa.
    """
    buckets: dict[str, dict] = {}

    def bucket(week: str) -> dict:
        return buckets.setdefault(
            week,
            {"week": week, "opened": 0, "closed": 0, "done": 0, "discarded": 0},
        )

    for r in rows:
        created, edited = r.get("created") or "", r.get("edited") or ""
        status = r.get("status") or ""
        if created:
            bucket(week_start(created))["opened"] += 1
        if status in CLOSED_STATUSES and edited:
            b = bucket(week_start(edited))
            b["closed"] += 1
            b["done" if status == "Done" else "discarded"] += 1

    weeks = [buckets[k] for k in sorted(buckets)]
    running = 0
    for w in weeks:
        w["net"] = w["opened"] - w["closed"]
        running += w["net"]
        w["running"] = running
    return weeks


def render_html(weeks: list[dict], totals: dict) -> str:
    """Render the weekly report as email-safe HTML.

    Deliberately CSS-bar charts on table cells rather than SVG — Gmail and the
    iOS Mail app strip or mangle inline SVG, and a report nobody can read on a
    phone is not a report.
    """
    recent = weeks[-12:]
    scale = max([w["opened"] for w in recent] + [w["closed"] for w in recent] + [1])
    peak = max(weeks, key=lambda w: w["running"])
    now = weeks[-1]

    def bar(value: int, colour: str) -> str:
        pct = round(value / scale * 100)
        return (
            f'<div style="background:{colour};height:10px;width:{pct}%;'
            f'border-radius:3px;min-width:{2 if value else 0}px"></div>'
        )

    rows = []
    for w in recent:
        net = w["net"]
        net_col = "#eb6834" if net > 0 else "#2a78d6" if net < 0 else "#767c88"
        disc = f' <span style="color:#1baf7a">+{w["discarded"]} discarded</span>' if w["discarded"] else ""
        rows.append(f"""
        <tr>
          <td style="padding:7px 10px;font-family:monospace;font-size:13px;white-space:nowrap">{w["week"]}</td>
          <td style="padding:7px 10px;width:35%">{bar(w["opened"], "#eb6834")}</td>
          <td style="padding:7px 10px;font-family:monospace;font-size:13px;text-align:right">{w["opened"]}</td>
          <td style="padding:7px 10px;width:35%">{bar(w["closed"], "#2a78d6")}</td>
          <td style="padding:7px 10px;font-family:monospace;font-size:13px;text-align:right">{w["closed"]}{disc}</td>
          <td style="padding:7px 10px;font-family:monospace;font-size:13px;text-align:right;color:{net_col}">
            {"+" if net >= 0 else ""}{net}</td>
          <td style="padding:7px 10px;font-family:monospace;font-size:13px;text-align:right;font-weight:600">{w["running"]}</td>
        </tr>""")

    trend = now["running"] - weeks[-2]["running"] if len(weeks) > 1 else 0
    verdict = (
        "The backlog shrank this week."
        if trend < 0
        else "The backlog grew this week."
        if trend > 0
        else "The backlog held level this week."
    )

    return f"""<div style="font-family:-apple-system,Segoe UI,sans-serif;color:#16181d;max-width:720px">
  <h2 style="margin:0 0 4px;font-size:20px">Task flow, week ending {now["week"]}</h2>
  <p style="margin:0 0 20px;color:#4a4f5a;font-size:14px">{verdict}</p>

  <table cellpadding="0" cellspacing="0" style="width:100%;margin-bottom:22px">
    <tr>
      <td style="padding:12px 14px;background:#f4f5f7;border-radius:8px">
        <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#767c88">Open now</div>
        <div style="font-size:26px;font-weight:600;font-family:monospace">{now["running"]}</div>
      </td>
      <td style="width:10px"></td>
      <td style="padding:12px 14px;background:#f4f5f7;border-radius:8px">
        <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#767c88">This week</div>
        <div style="font-size:26px;font-weight:600;font-family:monospace">{"+" if now["net"] >= 0 else ""}{now["net"]}</div>
      </td>
      <td style="width:10px"></td>
      <td style="padding:12px 14px;background:#f4f5f7;border-radius:8px">
        <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#767c88">Peak</div>
        <div style="font-size:26px;font-weight:600;font-family:monospace">{peak["running"]}</div>
      </td>
      <td style="width:10px"></td>
      <td style="padding:12px 14px;background:#f4f5f7;border-radius:8px">
        <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#767c88">Created ever</div>
        <div style="font-size:26px;font-weight:600;font-family:monospace">{totals["created"]}</div>
      </td>
    </tr>
  </table>

  <table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">
    <tr style="font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#767c88;text-align:left">
      <th style="padding:6px 10px">Week</th>
      <th style="padding:6px 10px" colspan="2">Opened</th>
      <th style="padding:6px 10px" colspan="2">Closed</th>
      <th style="padding:6px 10px;text-align:right">Net</th>
      <th style="padding:6px 10px;text-align:right">Open</th>
    </tr>
    {"".join(rows)}
  </table>

  <p style="color:#767c88;font-size:12px;line-height:1.5;margin-top:22px">
    Last 12 weeks. Opened comes from each task's creation timestamp and is exact.
    Closed is inferred from the last-edited timestamp of tasks now Done or Discarded,
    because Notion does not record when a status changed — a closed task edited later
    lands in the week of that edit, so recent closure counts can run slightly high.
  </p>
</div>"""
