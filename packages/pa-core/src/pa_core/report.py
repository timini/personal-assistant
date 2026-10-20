"""Deterministic HTML reports with optional, evidence-bound LLM insights."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date as date_type, datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, select_autoescape

from pa_core.config import PA_ROOT, get_assistant_name, get_now, get_user_config
from pa_core.daily_log import get_events


REPORTS_DIR = PA_ROOT / "activity" / "reports"
CLOSED_STATUSES = {"Done", "Discarded"}


@dataclass
class ReportBundle:
    report_id: str
    kind: str
    date: str
    facts: dict[str, Any]
    insights: dict[str, Any] | None
    html_path: Path
    manifest_path: Path


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ facts.title }}</title><style>
:root{color-scheme:light;--ink:#172033;--muted:#647087;--line:#dfe5ee;--panel:#f5f7fa;--blue:#2867d7;--green:#16865b;--red:#c34b36}
*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;background:#fff;padding:36px}.eyebrow{text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-size:11px}
h1{font-size:30px;line-height:1.15;margin:6px 0}h2{margin-top:32px;border-bottom:1px solid var(--line);padding-bottom:8px}h3{margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.card{background:var(--panel);border-radius:10px;padding:14px}
.metric{font:700 24px/1.1 ui-monospace,SFMono-Regular,monospace}.label{font-size:12px;color:var(--muted)}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:12px}
.bar{height:9px;background:var(--blue);border-radius:4px}.done{color:var(--green)}.warn{color:var(--red)}.insights{border-left:4px solid var(--blue);padding-left:18px}
footer{margin-top:36px;color:var(--muted);font-size:12px}@media(max-width:600px){main{padding:22px 16px}h1{font-size:25px}}
@media print{body{background:#fff}main{max-width:none;padding:0}}
</style></head><body><main>
<div class="eyebrow">{{ facts.kind }} report · {{ facts.date }}</div><h1>{{ facts.title }}</h1>
{% if insights %}<section class="insights"><h2>Insights</h2><p>{{ insights.summary }}</p>
{% if insights.insights %}<h3>What stands out</h3><ul>{% for x in insights.insights %}<li>{{ x.text }}</li>{% endfor %}</ul>{% endif %}
{% if insights.watchouts %}<h3>Watchouts</h3><ul>{% for x in insights.watchouts %}<li>{{ x.text }}</li>{% endfor %}</ul>{% endif %}
{% if insights.next_actions %}<h3>Suggested next actions</h3><ul>{% for x in insights.next_actions %}<li>{{ x.text }}</li>{% endfor %}</ul>{% endif %}</section>{% endif %}
{% if facts.health %}<section><h2>Health</h2><div class="grid">
{% for key,label,suffix in [('sleep_hours','Sleep','h'),('resting_hr','Resting HR',' bpm'),('avg_stress','Average stress',''),('body_battery_high','Body Battery high',''),('steps','Steps','')] %}
{% if facts.health.get(key) is not none %}<div class="card"><div class="metric">{{ facts.health[key] }}{{ suffix }}</div><div class="label">{{ label }}</div></div>{% endif %}{% endfor %}</div></section>{% endif %}
{% if facts.activities %}<section><h2>Fitness</h2>{% for a in facts.activities %}<div class="card"><h3>{{ a.name }}</h3><div class="grid">
<div><div class="metric">{{ a.distance_km }} km</div><div class="label">Distance</div></div><div><div class="metric">{{ a.duration }}</div><div class="label">Duration</div></div>
<div><div class="metric">{{ a.pace }}</div><div class="label">Average pace</div></div>{% if a.average_hr %}<div><div class="metric">{{ a.average_hr }}</div><div class="label">Average HR</div></div>{% endif %}
</div></div>{% endfor %}</section>{% endif %}
{% if facts.habits %}<section><h2>Habits</h2><table><thead><tr><th>Habit</th><th>Today</th><th>Streak</th></tr></thead><tbody>
{% for h in facts.habits %}<tr><td>{{ h.emoji }} {{ h.name }}</td><td class="{{ 'done' if h.status == 'completed' else 'warn' if h.status == 'skipped' else '' }}">{{ h.status|replace('_',' ')|title }}</td><td>{{ h.streak }} days</td></tr>{% endfor %}</tbody></table></section>{% endif %}
{% if facts.tasks %}<section><h2>Task burndown</h2><div class="grid"><div class="card"><div class="metric">{{ facts.tasks.live }}</div><div class="label">Live now</div></div>
<div class="card"><div class="metric">{{ facts.tasks.completed_today }}</div><div class="label">Completed today</div></div><div class="card"><div class="metric">{{ facts.tasks.start - facts.tasks.live }}</div><div class="label">Net reduction today</div></div></div>
<p><code>{{ facts.tasks.start }} + {{ facts.tasks.created_today }} created − {{ facts.tasks.completed_today }} completed − {{ facts.tasks.discarded_today }} discarded = {{ facts.tasks.live }}</code></p>
{% if facts.tasks.by_project %}<h3>Live tasks by project</h3><table><tbody>{% for name,value in facts.tasks.by_project|dictsort(false,'value')|reverse %}<tr><td>{{ name }}</td><td>{{ value }}</td></tr>{% endfor %}</tbody></table>{% endif %}
{% if facts.tasks.trend %}<h3>Seven-day completions</h3><table><tbody>{% for d in facts.tasks.trend %}<tr><td>{{ d.date }}</td><td style="width:55%"><div class="bar" style="width:{{ d.width }}%"></div></td><td>{{ d.completed }}</td></tr>{% endfor %}</tbody></table>{% endif %}
<p class="label">Older completion dates are inferred from Notion's last-edited timestamp; today's activity-log count is exact.</p></section>{% endif %}
{% if facts.calendar %}<section><h2>Calendar</h2><table><tbody>{% for event in facts.calendar %}<tr><td>{{ event.time|default(event.start|default(event.start_time|default(''))) }}</td><td>{{ event.summary|default(event.title|default('Untitled event')) }}</td><td>{{ event.calendar or '' }}</td></tr>{% endfor %}</tbody></table></section>{% endif %}
{% if facts.sections %}{% for section in facts.sections %}<section><h2>{{ section.heading }}</h2>
{% for paragraph in section.paragraphs|default([]) %}<p>{{ paragraph }}</p>{% endfor %}
{% if section.bullets|default([]) %}<ul>{% for bullet in section.bullets %}<li>{{ bullet }}</li>{% endfor %}</ul>{% endif %}
{% if section.sources|default([]) %}<h3>Sources</h3><ul>{% for source in section.sources %}<li><a href="{{ source.url }}">{{ source.label }}</a></li>{% endfor %}</ul>{% endif %}
</section>{% endfor %}{% endif %}
{% if facts.wins %}<section><h2>Wins</h2><ul>{% for win in facts.wins %}<li>{{ win }}</li>{% endfor %}</ul></section>{% endif %}
{% if facts.warnings %}<section><h2>Heads up</h2><ul>{% for warning in facts.warnings %}<li>{{ warning }}</li>{% endfor %}</ul></section>{% endif %}
<footer>Generated deterministically by {{ assistant_name }}. LLM-written observations, when present, appear only in the Insights section.</footer>
</main></body></html>"""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _facts_hash(facts: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(facts).encode()).hexdigest()


def render_html(facts: dict[str, Any], insights: dict[str, Any] | None) -> str:
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True))
    return env.from_string(_TEMPLATE).render(
        facts=facts, insights=insights, assistant_name=get_assistant_name()
    )


def _duration(seconds: float | int | None) -> str:
    seconds = int(round(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _pace(seconds: float | int | None, metres: float | int | None) -> str:
    if not seconds or not metres:
        return "—"
    pace = int(round(float(seconds) / (float(metres) / 1000)))
    return f"{pace // 60}:{pace % 60:02d}/km"


def _activities(date_str: str) -> list[dict[str, Any]]:
    try:
        from pa_health.client import _authenticated_client
        rows = _authenticated_client().get_activities_by_date(date_str, date_str)
    except Exception:
        return []
    result = []
    for row in rows or []:
        metres = row.get("distance") or 0
        seconds = row.get("duration") or 0
        result.append({
            "name": row.get("activityName") or row.get("activityType", {}).get("typeKey", "Activity").title(),
            "distance_km": round(metres / 1000, 2), "duration": _duration(seconds),
            "pace": _pace(seconds, metres), "average_hr": row.get("averageHR"),
            "max_hr": row.get("maxHR"), "calories": row.get("calories"),
        })
    return sorted(result, key=lambda x: x["name"].casefold())


def _task_facts(date_str: str, events: list[dict]) -> dict[str, Any]:
    try:
        from pa_notion.client import NotionClient
        from pa_core.config import get_secret
        pages = NotionClient().query_database(get_secret("NOTION_TASKS_DB_ID"))
    except Exception:
        pages = []
    status_counts: Counter[str] = Counter()
    project_counts: Counter[str] = Counter()
    inferred: Counter[str] = Counter()
    for page in pages:
        props = page.get("properties", {})
        status = ((props.get("Status", {}).get("select") or {}).get("name") or "No status")
        project = ((props.get("Project", {}).get("select") or {}).get("name") or "No project")
        status_counts[status] += 1
        if status not in CLOSED_STATUSES:
            project_counts[project] += 1
        if status in CLOSED_STATUSES and page.get("last_edited_time"):
            inferred[page["last_edited_time"][:10]] += 1
    live = sum(project_counts.values())
    unique = lambda action: {e.get("summary") for e in events if e.get("category") == "task" and e.get("action") == action}
    completed = len(unique("completed")); created = len(unique("created")); discarded = len(unique("discarded"))
    start = live - created + completed + discarded
    end = date_type.fromisoformat(date_str)
    days = [(end - timedelta(days=n)).isoformat() for n in range(6, -1, -1)]
    values = [completed if day == date_str else inferred[day] for day in days]
    peak = max(values + [1])
    trend = [{"date": day, "completed": value, "width": round(value / peak * 100)} for day, value in zip(days, values)]
    return {"live": live, "start": start, "created_today": created, "completed_today": completed,
            "discarded_today": discarded, "by_status": dict(sorted(status_counts.items())),
            "by_project": dict(sorted(project_counts.items())), "trend": trend}


def collect_daily_facts(date: str | None = None, kind: str = "daily") -> dict[str, Any]:
    date_str = date or get_now()["date"]
    events = get_events(date_str)
    try:
        from pa_core.context import _fetch_calendar, _fetch_habits, _fetch_health
        health, habits = _fetch_health(date_str), _fetch_habits(date_str)
        calendar = _fetch_calendar() if date_str == get_now()["date"] else []
    except Exception:
        health, habits, calendar = {}, [], []
    wins = []
    warnings = []
    for event in events:
        if event.get("action") == "completed":
            wins.append(event.get("summary", ""))
        if event.get("action") == "flagged":
            warnings.append(event.get("summary", ""))
    label = {"daily": "Full Daily", "health": "Health & Fitness", "tasks": "Task Flow"}.get(kind, kind.title())
    return {"kind": kind, "date": date_str, "title": f"{get_assistant_name()} {label} Report",
            "health": health if kind != "tasks" else {}, "activities": _activities(date_str) if kind != "tasks" else [],
            "habits": habits if kind != "tasks" else [], "tasks": _task_facts(date_str, events) if kind != "health" else {},
            "calendar": calendar, "wins": sorted(set(filter(None, wins))), "warnings": sorted(set(filter(None, warnings))),
            "sections": []}


def load_research_facts(path: Path, date: str | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not payload.get("title") or not isinstance(payload.get("sections"), list):
        raise ValueError("Research input requires title and ordered sections")
    return {"kind": "research", "date": date or get_now()["date"], "title": payload["title"],
            "sections": payload["sections"], "health": {}, "activities": [], "habits": [], "tasks": {},
            "calendar": [], "wins": payload.get("wins", []), "warnings": payload.get("warnings", [])}


def _evidence_paths(value: Any, prefix: str = "") -> set[str]:
    paths = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.add(path); paths |= _evidence_paths(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            paths.add(path); paths |= _evidence_paths(child, path)
    return paths


def _valid_insights(result: Any, facts: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or not isinstance(result.get("summary"), str):
        return False
    evidence = _evidence_paths(facts)
    for section in ("insights", "watchouts", "next_actions"):
        if not isinstance(result.get(section), list):
            return False
        for item in result[section]:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                return False
            if any(key not in evidence for key in item.get("evidence_keys", [])):
                return False
    return True


def _run_claude(facts: dict[str, Any]) -> dict[str, Any]:
    schema = {"type": "object", "properties": {
        "summary": {"type": "string"},
        **{name: {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "evidence_keys": {"type": "array", "items": {"type": "string"}}
        }, "required": ["text", "evidence_keys"]}} for name in ("insights", "watchouts", "next_actions")}},
        "required": ["summary", "insights", "watchouts", "next_actions"]}
    prompt = ("Write concise personal-report insights using only the supplied facts. Do not invent numbers or facts. "
              "Every item must cite one or more dotted evidence keys from the input. Return at most 4 insights, "
              "3 watchouts and 3 next actions. Facts:\n" + _canonical(facts))
    model = get_user_config().get("reports", {}).get("llm_model", "sonnet")
    proc = subprocess.run(["claude", "-p", "--no-session-persistence", "--permission-mode", "dontAsk", "--model", model,
                           "--allowedTools", "", "--output-format", "json", "--json-schema", json.dumps(schema), prompt],
                          capture_output=True, text=True, timeout=90, check=True)
    wrapper = json.loads(proc.stdout)
    result = wrapper.get("structured_output", wrapper)
    if isinstance(result, str): result = json.loads(result)
    return result


def generate_insights(facts: dict[str, Any], cache_dir: Path) -> dict[str, Any] | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{_facts_hash(facts)}.json"
    if cache.exists():
        try:
            value = json.loads(cache.read_text())
            return value if _valid_insights(value, facts) else None
        except Exception:
            return None
    try:
        value = _run_claude(facts)
    except Exception:
        return None
    if not _valid_insights(value, facts):
        return None
    cache.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    return value


def generate_report(kind: str = "daily", date: str | None = None, input_path: Path | None = None,
                    output_root: Path | None = None, insights: bool = True) -> ReportBundle:
    date_str = date or get_now()["date"]
    facts = load_research_facts(input_path, date_str) if kind == "research" and input_path else collect_daily_facts(date_str, kind)
    if kind == "research" and not input_path:
        raise ValueError("Research reports require --input JSON")
    report_id = f"{kind}-{date_str}"
    root = (output_root or REPORTS_DIR) / date_str
    root.mkdir(parents=True, exist_ok=True)
    insights_enabled = get_user_config().get("reports", {}).get("insights_enabled", True)
    generated_insights = generate_insights(facts, root / ".insights") if insights and insights_enabled else None
    html_path = root / f"{date_str}-{kind}-report.html"
    manifest_path = root / f"{date_str}-{kind}-manifest.json"
    html_path.write_text(render_html(facts, generated_insights), encoding="utf-8")
    manifest_path.write_text(json.dumps({"report_id": report_id, "kind": kind, "date": date_str,
        "facts_sha256": _facts_hash(facts), "html": html_path.name, "deliveries": {}}, indent=2))
    return ReportBundle(report_id, kind, date_str, facts, generated_insights, html_path, manifest_path)


def deliver_report(bundle: ReportBundle) -> dict[str, dict[str, Any]]:
    from pa_google.reports import email_report, publish_report
    results: dict[str, dict[str, Any]] = {}
    drive_url = None
    try:
        published = publish_report(bundle.html_path, bundle.report_id)
        drive_url = published["url"]
        results["drive"] = {"ok": True, **published}
    except Exception as exc:
        results["drive"] = {"ok": False, "error": str(exc)}
    try:
        sent = email_report(bundle.html_path, bundle.facts["title"], drive_url)
        results["email"] = {"ok": True, **sent}
    except Exception as exc:
        results["email"] = {"ok": False, "error": str(exc)}
    manifest = json.loads(bundle.manifest_path.read_text())
    manifest["deliveries"] = results
    bundle.manifest_path.write_text(json.dumps(manifest, indent=2))
    return results
